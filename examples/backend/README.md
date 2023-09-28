This README gives some examples on backend-specific model workflow.

# XNNPACK Backend

[XNNPACK](https://github.com/google/XNNPACK) is a library of optimized of neural network inference operators for ARM and x86 platforms. Our delegate lowers models to run using these highly optimized CPU operators. You can try out lowering and running some example models using the following commands:

## XNNPACK delegation-only

The following command will produce an floating-point XNNPACK delegated model `mv2_xnnpack_fp32.pte` that can be run using XNNPACK's operators. It will also print out the lowered graph, showing what parts of the models have been lowered to XNNPACK via `executorch_call_delegate`.

```bash
# For MobileNet V2
python3 -m examples.backend.xnnpack_examples --model_name="mv2" --delegate
```

Once we have the model binary (pte) file, then let's run it with ExecuTorch runtime using the `xnn_executor_runner`.

```bash
buck2 run examples/backend:xnn_executor_runner -- --model_path ./mv2_xnnpack_fp32.pte
```

## XNNPACK quantization + delegation
The following command will produce an XNNPACK quantized and delegated model `mv2_xnnpack_q8.pte` that can be run using XNNPACK's operators. It will also print out the lowered graph, showing what parts of the models have been lowered to XNNPACK via `executorch_call_delegate`.

```bash
python3 -m examples.backend.xnnpack_examples --model_name="mv2" --quantize --delegate
```

Once we have the model binary (pte) file, then let's run it with ExecuTorch runtime using the `xnn_executor_runner`.

```bash
buck2 run examples/backend:xnn_executor_runner -- --model_path ./mv2_xnnpack_q8.pte
```

## XNNPACK performance gain

### Overview

We tested the performance for MobileNet V2 and MobileNet V3 on Linux x86 and Mac (Apple Silicon) platforms.

For each model, we export three variations: portable (without any optimization), xnnpack fp32 (exported for XNNPACK delegation without quantization), xnnpack q8 (exported for XNNPACK delegation with qint8 delegation).

We build the benchmarking binary (will be released in the near future, but it is similar to `examples/backend:xnn_executor_runner`). Benchmarking binary, by default, runs 10 iterations of warmup and 50 iterations of benchmarking. Number reported here are average measured latency, in ms, across 50 runs. The first iteration is slower due to warm up, and the performance is is stable on subsequent iterations, so we also report the execution time for the first iteration for reference. Below is the model execution time for first iteration and subsequent iterations (average after warmup), in milliseconds. We use a single thread to test the models. Details about the methodology and repro steps are below the tables.

### Methodology

Models are exported with the steps above for XNNPACK delegation, and with `examples/export:export_example` for portable backend without any optimization. Then use `//examples/backend:xnn_executor_runner` with profiler (command listed below); or  in the future, use the runtime in `//sdk/runners:executor_runner` since it gives more options such as number of iterations after build rules for OSS is added.

```
buck run -c executorch.prof_enabled=true -c executorch.prof_buf_size=8096 -c executorch.num_prof_blocks=61 //examples/backend:xnn_executor_runner -- --model_path mv3.pte
```

A rough number of execution time can be obtained via the log timestamp. The profiler result can be analyzed with `profiler:profiler_results_cli`.

```
buck run //profiler:profiler_results_cli -- --prof_results_bin=prof_result.bin
```

Run: Use 60 iterations. Usually the first iteration is slower, due to warm up. However, the performance from the second iteration is quite stable and reliable. We note down the execution time for first iteration; then for average execution time, we drop the first 10 iterations, and calculate the average time for the next 50 iterations.

Number we use: “run model” time in the profiler_results_cli tool. This represents the time to execute a model for an iteration. The numbers in the report are floored.

### Results

MobileNet V2 - Linux x86

| backend      | first iteration (ms) | subsequent iteration (ms) |
|--------------|----------------------|---------------------------|
| portable     | 25690                | 25480                     |
| xnnpack fp32 | 21                   | 10                        |
| xnnpack q8   | 18                   | 11                        |


MobileNet V2 - Mac

| backend      | first iteration (ms) | subsequent iteration (ms) |
|--------------|----------------------|---------------------------|
| portable     | 17743                | 17852                     |
| xnnpack fp32 | 21                   | 16                        |
| xnnpack q8   | 20                   | 18                        |


MobileNet V3 - Linux x86

| backend      | first iteration (ms) | subsequent iteration (ms) |
|--------------|----------------------|---------------------------|
| portable     | 4938                 | 4975                      |
| xnnpack fp32 | 15                   | 8                         |
| xnnpack q8   | 343                  | 323                       |

Note: MV3 does not have quantized hardsigomid and hardswish, this is because XNNPACK currently does not support quantized hardswish and hardsigmoid. Our current quantized partitioner only partitions quantized operators, so we do not lower these floating point ops, and they are run on portable. Ops running on portable lead to the worse performance for MV3 q8. We will eventually release a mixed datatype partitioner to fix this

MobileNet V3 - Mac

| backend      | first iteration (ms) | subsequent iteration (ms) |
|--------------|----------------------|---------------------------|
| portable     | 3427                 | 3394                      |
| xnnpack fp32 | 7                    | 4                         |
| xnnpack q8   | 206                  | 201                       |