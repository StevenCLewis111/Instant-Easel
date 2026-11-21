"""
esr_convert.py: turns Real-ESRGAN's official realesr-general-x4v3.pth (xinntao/Real-ESRGAN, BSD-3-Clause) into an ONNX model
for AI Upscale, without PyTorch. The build runs it once (python esr_convert.py <in.pth> <out.onnx>); the app only uses the result.

The .pth is read with a locked-down unpickler that accepts nothing but tensors and their storage (no other code can run from
it); the network (SRVGGNetCompact: 33 3x3 convolutions with PReLU, then a 4x pixel shuffle plus the picture enlarged) is
rebuilt as an ONNX graph with those weights.
"""
import io, pickle, sys, zipfile
from collections import OrderedDict
import numpy as np

_DT = {"FloatStorage": np.float32, "HalfStorage": np.float16, "DoubleStorage": np.float64, "LongStorage": np.int64, "IntStorage": np.int32}


def load_pth(path):
    """the state dict of a PyTorch zip checkpoint, as numpy arrays"""
    z = zipfile.ZipFile(path); root = z.namelist()[0].split("/")[0]

    class _Storage:
        def __init__(self, name): self.name = name

    def _rebuild(storage, offset, size, stride, *rest):
        dt, key = storage
        raw = np.frombuffer(z.read(f"{root}/data/{key}"), dtype=dt)
        if not size: return raw[offset:offset + 1].reshape(()).copy()
        return np.lib.stride_tricks.as_strided(raw[offset:], shape=tuple(size), strides=tuple(s * raw.itemsize for s in stride)).copy()

    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if mod == "torch._utils" and name == "_rebuild_tensor_v2": return _rebuild
            if mod == "collections" and name == "OrderedDict": return OrderedDict
            if mod == "torch" and name in _DT: return _Storage(name)
            raise pickle.UnpicklingError(f"not allowed in a model file: {mod}.{name}")
        def persistent_load(self, pid):
            kind, stype, key = pid[0], pid[1], pid[2]
            if kind != "storage": raise pickle.UnpicklingError("unexpected data")
            return (_DT[stype.name if isinstance(stype, _Storage) else str(stype).split(".")[-1]], key)

    d = U(io.BytesIO(z.read(f"{root}/data.pkl"))).load()
    for k in ("params_ema", "params"):
        if isinstance(d, dict) and k in d: d = d[k]; break
    return d


def build(sd, out_path, scale=4):
    import onnx
    from onnx import helper, TensorProto, numpy_helper
    convs = sorted({int(k.split(".")[1]) for k in sd if k.endswith(".bias") and sd[k].ndim == 1 and k.replace("bias", "weight") in sd and sd[k.replace("bias", "weight")].ndim == 4})
    nodes, inits = [], []; cur = "input"
    def init(name, arr): inits.append(numpy_helper.from_array(np.ascontiguousarray(arr, np.float32), name)); return name
    for i, c in enumerate(convs):
        w, b = sd[f"body.{c}.weight"], sd[f"body.{c}.bias"]
        o = f"conv{i}"; nodes.append(helper.make_node("Conv", [cur, init(f"w{i}", w), init(f"b{i}", b)], [o], pads=[1, 1, 1, 1], kernel_shape=[3, 3])); cur = o
        pk = f"body.{c + 1}.weight"
        if i < len(convs) - 1 and pk in sd:
            o = f"act{i}"; nodes.append(helper.make_node("PRelu", [cur, init(f"a{i}", sd[pk].reshape(-1, 1, 1))], [o])); cur = o
    nodes.append(helper.make_node("DepthToSpace", [cur], ["shuf"], blocksize=scale, mode="CRD"))
    nodes.append(helper.make_node("Resize", ["input", "", init("scales", np.array([1, 1, scale, scale], np.float32))], ["base"], mode="nearest"))
    nodes.append(helper.make_node("Add", ["shuf", "base"], ["output"]))
    g = helper.make_graph(nodes, "realesr_general_x4v3", [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, None, None])],
                          [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3, None, None])], inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)], producer_name="Instant Easel esr_convert"); m.ir_version = 8
    onnx.checker.check_model(m); onnx.save(m, out_path)


if __name__ == "__main__":
    build(load_pth(sys.argv[1]), sys.argv[2])
    print("converted:", sys.argv[2])
