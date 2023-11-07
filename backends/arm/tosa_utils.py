import logging
import os

import numpy as np
import serializer.tosa_serializer as ts
from executorch.backends.arm.tosa_mapping import TosaArg
from serializer.tosa_serializer import TosaOp

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
TOSA_DBG_VERBOSE = os.environ.get("TOSA_DBG_VERBOSE") == "1"
if TOSA_DBG_VERBOSE:
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)


def dbg_node(node):
    # Debug output of node information
    logger.info("OP")
    logger.info(f"  op is {node.op}")
    logger.info(f"  name is {node.name}")
    logger.info(f"  node target is {node.target}")
    logger.info(f"  node args is {node.args}")
    logger.info(f"  node kwargs is {node.kwargs}")
    logger.info("  node.meta = ")
    for k, v in node.meta.items():
        logger.info(f"    '{k}' = {v}")
        if type([]) == type(v):
            for i in v:
                logger.info(f"      {i} ")


# Output TOSA flatbuffer and test harness file
def dbg_tosa_dump(tosa_graph, path):
    filename = "output.tosa"

    logger.info(f"Emitting debug output to {path}")

    os.makedirs(path, exist_ok=True)

    fb = tosa_graph.serialize()
    js = tosa_graph.writeJson(filename)

    with open(path + filename, "wb") as f:
        f.write(fb)

    with open(path + "desc.json", "w") as f:
        f.write(js)


def dbg_fail(node, tosa_graph, path):
    dbg_tosa_dump(tosa_graph, path)
    logger.warn("Internal error due to poorly handled node:")
    dbg_node(node)
    logger.warn(f"Debug output captured in '{path}'.")
    raise RuntimeError("TOSA Internal Error on node, enable logging for further info")


# Helper function to match TOSA's broadcasting rank requirement
# Ref: TOSA 0.80.0 specification - 1.9.3. Data Layouts from
# https://www.mlplatform.org/tosa/tosa_spec.html
def promote_shape(tosa_fb, arg, promoted_shape, out_dtype):
    assert np.prod(arg.shape) == np.prod(promoted_shape), "Incompatible promoted shape"
    reshape_res = tosa_fb.addIntermediate(promoted_shape, out_dtype)
    attr = ts.TosaSerializerAttribute()
    attr.ReshapeAttribute(promoted_shape)
    tosa_fb.addOperator(TosaOp.Op().RESHAPE, [arg.name], [reshape_res.name], attr)
    return reshape_res


# Helper transpose function to match TOSA's shape requirements
# E.g., TOSA 0.80.0 specification - 2.3.3 CONV2D shapes:
# https://www.mlplatform.org/tosa/tosa_spec.html#_conv2d
def transpose_helper(tosa_fb, input, new_order, out_dtype):
    # Check new_order's length is equal to input rank
    assert len(input.shape) == len(new_order), "Wrong shape order length"

    # Check no duplications
    assert len(set(new_order)) == len(new_order), "Contain duplicated dim numbers"

    # Check all dims are valid
    for idx in new_order:
        if idx < 0:
            assert True, "Negative dim number"
        elif idx >= len(input.shape):
            assert True, "Dim is greater than input rank"

    input_shape_transpoed = [input.shape[i] for i in new_order]
    attr = ts.TosaSerializerAttribute()
    attr.TransposeAttribute(new_order)
    input_transposed = tosa_fb.addIntermediate(input_shape_transpoed, out_dtype)
    tosa_fb.addOperator(
        TosaOp.Op().TRANSPOSE, [input.name], [input_transposed.name], attr
    )
    return input_transposed


def getNodeArgs(node):
    return [TosaArg(arg) for arg in node.args]


# Helper function to do broadcasting
# Ref: https://www.mlplatform.org/tosa/tosa_spec.html#_broadcasting
def broadcastShapes(shape1, shape2):
    assert len(shape1) == len(shape2), "broadcastShape::shapes must have same ranks"

    need_broadcasting = False
    for val1, val2 in zip(shape1, shape2):
        if val1 != val2:
            need_broadcasting = True
    if not need_broadcasting:
        return shape1

    broadcasted_shape = list(shape1)
    shape2 = list(shape2)
    for idx, _ in enumerate(broadcasted_shape):
        if broadcasted_shape[idx] == 1:
            broadcasted_shape[idx] = shape2[idx]
        else:
            assert not (
                shape2[idx] != 1 and shape2[idx] != broadcasted_shape[idx]
            ), "broadcastShape::broadcast shape mismatch"

    return broadcasted_shape