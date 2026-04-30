import argparse
import json
from pathlib import Path

import joblib
import numpy as np


def go_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def format_int_slice(values, type_name="int32", chunk_size=24):
    if len(values) == 0:
        return f"[] {type_name}{{}}".replace(" ", "")
    lines = [f"[]{type_name}{{"]
    for i in range(0, len(values), chunk_size):
        chunk = values[i:i + chunk_size]
        lines.append("    " + ", ".join(str(int(v)) for v in chunk) + ",")
    lines.append("}")
    return "\n".join(lines)


def format_float_slice(values, chunk_size=12):
    if len(values) == 0:
        return "[]float64{}"
    lines = ["[]float64{"]
    for i in range(0, len(values), chunk_size):
        chunk = values[i:i + chunk_size]
        lines.append("    " + ", ".join(repr(float(v)) for v in chunk) + ",")
    lines.append("}")
    return "\n".join(lines)


def format_string_slice(values, chunk_size=6):
    if len(values) == 0:
        return "[]string{}"
    lines = ["[]string{"]
    for i in range(0, len(values), chunk_size):
        chunk = values[i:i + chunk_size]
        lines.append("    " + ", ".join(go_string(v) for v in chunk) + ",")
    lines.append("}")
    return "\n".join(lines)


def format_uint16_2d(list_of_lists, var_name):
    lines = [f"var {var_name} = [][]uint16{{"]
    for arr in list_of_lists:
        if len(arr) == 0:
            lines.append("    {},")
            continue
        values = ", ".join(str(int(v)) for v in arr)
        lines.append(f"    {{{values}}},")
    lines.append("}")
    return "\n".join(lines)


def format_string_uint32_map(var_name, classes):
    lines = [f"var {var_name} = map[string]uint32{{"]
    for idx, key in enumerate(classes):
        lines.append(f"    {go_string(str(key))}: {idx},")
    lines.append("}")
    return "\n".join(lines)


def compute_leaf_payloads(model, top_n):
    tree = model.tree_
    node_count = tree.node_count
    children_left = tree.children_left
    leaf_nodes = np.where(children_left == -1)[0]

    payload_index = np.full(node_count, -1, dtype=np.int32)
    leaf_default = []
    leaf_hybrid = []

    for payload_id, node_id in enumerate(leaf_nodes):
        payload_index[node_id] = payload_id
        counts = tree.value[node_id]
        total = counts.sum(axis=1)
        p1 = np.divide(
            counts[:, 1],
            total,
            out=np.zeros_like(total, dtype=np.float64),
            where=total > 0
        )
        default_idx = np.where(p1 >= 0.5)[0].astype(np.uint16).tolist()
        top_indices = np.argsort(-p1)[:top_n].astype(np.uint16).tolist()

        if len(default_idx) >= top_n:
            hybrid_idx = default_idx
        else:
            hybrid_idx = list(default_idx)
            selected = set(hybrid_idx)
            need = top_n - len(default_idx)
            for idx in top_indices:
                idx_int = int(idx)
                if idx_int not in selected:
                    hybrid_idx.append(idx_int)
                    selected.add(idx_int)
                    need -= 1
                    if need == 0:
                        break

        leaf_default.append(default_idx)
        leaf_hybrid.append(hybrid_idx)

    return payload_index, leaf_default, leaf_hybrid


def generate_go_code(save_data, package_name, top_n):
    model = save_data["model"]
    le_to = save_data["le_to"]
    le_code_hash = save_data.get("le_code_hash")
    le_sel = save_data["le_sel"]
    le_param = save_data["le_param"]
    le_param2 = save_data.get("le_param2")
    le_param3 = save_data.get("le_param3")
    le_from = save_data.get("le_from")
    le_value = save_data.get("le_value")
    mlb = save_data["mlb"]
    top_slots = save_data.get("top_slots", set())

    tree = model.tree_
    children_left = tree.children_left.astype(np.int32).tolist()
    children_right = tree.children_right.astype(np.int32).tolist()
    features = tree.feature.astype(np.int32).tolist()
    thresholds = tree.threshold.astype(np.float64).tolist()

    payload_index, leaf_default, leaf_hybrid = compute_leaf_payloads(model, top_n)
    payload_index_list = payload_index.tolist()

    slot_classes = [str(x) for x in mlb.classes_]
    to_classes = [str(x) for x in le_to.classes_]
    if le_code_hash:
        code_hash_classes = [str(x) for x in le_code_hash.classes_]
    sel_classes = [str(x) for x in le_sel.classes_]
    param_classes = [str(x) for x in le_param.classes_]
    if le_param2:
        param2_classes = [str(x) for x in le_param2.classes_]
    if le_param3:
        param3_classes = [str(x) for x in le_param3.classes_]
    if le_from:
        from_classes = [str(x) for x in le_from.classes_]
    if le_value:
        value_classes = [str(x) for x in le_value.classes_]

    code_parts = [
        f"package {package_name}",
        "",
        "const PrefetchTopK = 5000",
        f"const PrefetchTopN = {top_n}",
        "",
        f"var childrenLeft = {format_int_slice(children_left, 'int32')}",
        "",
        f"var childrenRight = {format_int_slice(children_right, 'int32')}",
        "",
        f"var splitFeature = {format_int_slice(features, 'int32')}",
        "",
        f"var splitThreshold = {format_float_slice(thresholds)}",
        "",
        f"var leafPayloadIndex = {format_int_slice(payload_index_list, 'int32')}",
        "",
        format_uint16_2d(leaf_default, "leafDefaultSlots"),
        "",
        format_uint16_2d(leaf_hybrid, "leafHybridSlots"),
        "",
        f"var slotClasses = {format_string_slice(slot_classes)}",
        "",
        format_string_uint32_map("toEncoder", to_classes),
        "",
    ]
    if le_code_hash:
        code_parts.extend([
            format_string_uint32_map("codeHashEncoder", code_hash_classes),
            "",
        ])
    code_parts.extend([
        format_string_uint32_map("selectorEncoder", sel_classes),
        "",
        format_string_uint32_map("paramEncoder", param_classes),
        "",
    ])
    if le_param2:
        code_parts.extend([format_string_uint32_map("param2Encoder", param2_classes), ""])
    if le_param3:
        code_parts.extend([format_string_uint32_map("param3Encoder", param3_classes), ""])
    if le_from:
        code_parts.extend([format_string_uint32_map("fromEncoder", from_classes), ""])
    if le_value:
        code_parts.extend([format_string_uint32_map("valueEncoder", value_classes), ""])
        
    code_parts.extend([
        "var topSlotSet = map[string]struct{}{",
    ])

    for slot in sorted(str(s) for s in top_slots):
        code_parts.append(f"    {go_string(slot)}: {{}},")
    code_parts.extend([
        "}",
        "",
        "func encodeOrZero(m map[string]uint32, key string) float64 {",
        "    if v, ok := m[key]; ok {",
        "        return float64(v)",
        "    }",
        "    return 0",
        "}",
        "",
    ])

    if le_code_hash:
        code_parts.extend([
            "func findLeaf(to string, codeHash string, selector string, inputParam1 string, inputParam2 string, inputParam3 string, fromAddr string, value string) int32 {",
            "    f0 := encodeOrZero(toEncoder, to)",
            "    f1 := encodeOrZero(codeHashEncoder, codeHash)",
            "    f2 := encodeOrZero(selectorEncoder, selector)",
            "    f3 := encodeOrZero(paramEncoder, inputParam1)",
            "    f4 := encodeOrZero(param2Encoder, inputParam2)",
            "    f5 := encodeOrZero(param3Encoder, inputParam3)",
            "    f6 := encodeOrZero(fromEncoder, fromAddr)",
            "    f7 := encodeOrZero(valueEncoder, value)",
            "    node := int32(0)",
            "    for {",
            "        left := childrenLeft[node]",
            "        if left == -1 {",
            "            return node",
            "        }",
            "        right := childrenRight[node]",
            "        feat := splitFeature[node]",
            "        thresh := splitThreshold[node]",
            "        var val float64",
            "        switch feat {",
            "        case 0:",
            "            val = f0",
            "        case 1:",
            "            val = f1",
            "        case 2:",
            "            val = f2",
            "        case 3:",
            "            val = f3",
            "        case 4:",
            "            val = f4",
            "        case 5:",
            "            val = f5",
            "        case 6:",
            "            val = f6",
            "        case 7:",
            "            val = f7",
            "        }",
            "        if val <= thresh {",
            "            node = left",
            "        } else {",
            "            node = right",
            "        }",
            "    }",
            "}",
            "",
            "func PredictSlotIndicesDefault(to string, codeHash string, selector string, inputParam1 string, inputParam2 string, inputParam3 string, fromAddr string, value string) []uint16 {",
            "    node := findLeaf(to, codeHash, selector, inputParam1, inputParam2, inputParam3, fromAddr, value)",
            "    payloadIdx := leafPayloadIndex[node]",
            "    if payloadIdx == -1 {",
            "        return nil",
            "    }",
            "    return leafDefaultSlots[payloadIdx]",
            "}",
            "",
            "func PredictSlotIndicesHybrid(to string, codeHash string, selector string, inputParam1 string, inputParam2 string, inputParam3 string, fromAddr string, value string) []uint16 {",
            "    node := findLeaf(to, codeHash, selector, inputParam1, inputParam2, inputParam3, fromAddr, value)",
            "    payloadIdx := leafPayloadIndex[node]",
            "    if payloadIdx == -1 {",
            "        return nil",
            "    }",
            "    return leafHybridSlots[payloadIdx]",
            "}",
            "",
            "func PredictSlotsDefault(to string, codeHash string, selector string, inputParam1 string, inputParam2 string, inputParam3 string, fromAddr string, value string) []string {",
            "    idx := PredictSlotIndicesDefault(to, codeHash, selector, inputParam1, inputParam2, inputParam3, fromAddr, value)",
            "    out := make([]string, len(idx))",
            "    for i, v := range idx {",
            "        out[i] = slotClasses[int(v)]",
            "    }",
            "    return out",
            "}",
            "",
            "func PredictSlotsHybrid(to string, codeHash string, selector string, inputParam1 string, inputParam2 string, inputParam3 string, fromAddr string, value string) []string {",
            "    idx := PredictSlotIndicesHybrid(to, codeHash, selector, inputParam1, inputParam2, inputParam3, fromAddr, value)",
            "    out := make([]string, len(idx))",
            "    for i, v := range idx {",
            "        out[i] = slotClasses[int(v)]",
            "    }",
            "    return out",
            "}",
            "",
        ])
    else:
        code_parts.extend([
            "func findLeaf(to string, selector string, inputParam1 string) int32 {",
            "    f0 := encodeOrZero(toEncoder, to)",
            "    f1 := encodeOrZero(selectorEncoder, selector)",
            "    f2 := encodeOrZero(paramEncoder, inputParam1)",
            "    node := int32(0)",
            "    for {",
            "        left := childrenLeft[node]",
            "        if left == -1 {",
            "            return node",
            "        }",
            "        feature := splitFeature[node]",
            "        threshold := splitThreshold[node]",
            "        value := 0.0",
            "        if feature == 0 {",
            "            value = f0",
            "        } else if feature == 1 {",
            "            value = f1",
            "        } else {",
            "            value = f2",
            "        }",
            "        if value <= threshold {",
            "            node = left",
            "        } else {",
            "            node = childrenRight[node]",
            "        }",
            "    }",
            "}",
            "",
            "func PredictSlotIndicesDefault(to string, selector string, inputParam1 string) []uint16 {",
            "    leaf := findLeaf(to, selector, inputParam1)",
            "    payload := leafPayloadIndex[leaf]",
            "    if payload < 0 {",
            "        return nil",
            "    }",
            "    return leafDefaultSlots[payload]",
            "}",
            "",
            "func PredictSlotIndicesHybrid(to string, selector string, inputParam1 string) []uint16 {",
            "    leaf := findLeaf(to, selector, inputParam1)",
            "    payload := leafPayloadIndex[leaf]",
            "    if payload < 0 {",
            "        return nil",
            "    }",
            "    return leafHybridSlots[payload]",
            "}",
            "",
            "func PredictSlotsDefault(to string, selector string, inputParam1 string) []string {",
            "    idx := PredictSlotIndicesDefault(to, selector, inputParam1)",
            "    out := make([]string, len(idx))",
            "    for i, v := range idx {",
            "        out[i] = slotClasses[int(v)]",
            "    }",
            "    return out",
            "}",
            "",
            "func PredictSlotsHybrid(to string, selector string, inputParam1 string) []string {",
            "    idx := PredictSlotIndicesHybrid(to, selector, inputParam1)",
            "    out := make([]string, len(idx))",
            "    for i, v := range idx {",
            "        out[i] = slotClasses[int(v)]",
            "    }",
            "    return out",
            "}",
            "",
        ])

    code_parts.extend([
        "func IsTopSlot(slot string) bool {",
        "    _, ok := topSlotSet[slot]",
        "    return ok",
        "}",
        "",
    ])
    return "\n".join(code_parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default="/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_k5000.pkl",
    )
    parser.add_argument(
        "--output",
        default="/home/tianyumao/workspace/transaction-replay/evm_analysis/prefetch_model_k5000_n20.go",
    )
    parser.add_argument("--package", default="prefetchmodel")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()

    save_data = joblib.load(args.model)
    go_code = generate_go_code(save_data, args.package, args.top_n)
    output_path = Path(args.output)
    output_path.write_text(go_code, encoding="utf-8")
    print(f"Generated Go model: {output_path}")


if __name__ == "__main__":
    main()
