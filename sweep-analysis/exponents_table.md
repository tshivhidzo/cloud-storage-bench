| Provider | Paradigm | Workload | beta | 95% CI | R2 | sat. | gated |
|---|---|---|---|---|---|---|---|
| alibaba | block | balanced | 0.012 | [0.002, 0.022] | 0.44 | c1 | 3 |
| alibaba | block | largeobj | -0.001 | [-0.002, 0.001] | 0.057 | c1 | 6 |
| alibaba | file | balanced | 0.419 | [0.269, 0.568] | 0.795 | c16 | 0 |
| alibaba | file | largeobj | 0.002 | [-0.006, 0.009] | 0.026 | c1 | 0 |
| alibaba | object | balanced | 0.998 | [0.95, 1.045] | 0.995 | c64 | 3 |
| alibaba | object | largeobj | 0.336 | [0.178, 0.494] | 0.692 | c16 | 0 |
| aws | block | balanced | 0.077 | [0.033, 0.121] | 0.6 | c4 | 0 |
| aws | block | largeobj | -0.004 | [-0.005, -0.003] | 0.891 | c1 | 9 |
| aws | file | balanced | 0.165 | [0.049, 0.282] | 0.501 | c16 | 5 |
| aws | file | largeobj | 0.031 | [-0.28, 0.342] | 0.005 | c16 | 5 |
| aws | object | balanced | 1.046 | [1.026, 1.067] | 0.999 | c64 | 0 |
| aws | object | largeobj | 0.577 | [0.428, 0.726] | 0.881 | c16 | 5 |
| azure | block | balanced | -0.16 | [-0.301, -0.019] | 0.39 | c4 | 0 |
| azure | block | largeobj | -0.002 | [-0.011, 0.006] | 0.031 | c1 | 7 |
| azure | file | balanced | 0.696 | [0.542, 0.85] | 0.91 | c16 | 0 |
| azure | file | largeobj | -0.028 | [-0.165, 0.109] | 0.02 | c4 | 0 |
| azure | object | balanced | 0.363 | [0.185, 0.541] | 0.674 | c16 | 6 |
| azure | object | largeobj | 0.368 | [0.2, 0.536] | 0.704 | c16 | 0 |
| gcp | block | balanced | 0.134 | [0.056, 0.211] | 0.596 | c4 | 0 |
| gcp | block | largeobj | -0.003 | [-0.004, -0.002] | 0.692 | c1 | 7 |
| gcp | file | balanced | 0.352 | [0.229, 0.476] | 0.801 | c64 | 0 |
| gcp | file | largeobj | 0.03 | [-0.029, 0.089] | 0.115 | c16 | 0 |
| gcp | object | balanced | 1.114 | [1.038, 1.19] | 0.991 | c64 | 0 |
| gcp | object | largeobj | 0.302 | [0.187, 0.418] | 0.772 | c16 | 6 |
| huawei | block | balanced | 0.194 | [0.085, 0.304] | 0.612 | c4 | 0 |
| huawei | block | largeobj | -0.003 | [-0.005, -0.001] | 0.599 | c1 | 9 |
| huawei | file | balanced | 0.165 | [0.119, 0.21] | 0.866 | c16 | 0 |
| huawei | file | largeobj | -0.001 | [-0.001, 0.0] | 0.16 | c1 | 0 |
| huawei | object | balanced | 0.875 | [0.785, 0.964] | 0.979 | c64 | 0 |
| huawei | object | largeobj | 0.304 | [0.128, 0.481] | 0.596 | c4 | 0 |

Pooled model: H4 (provider-dependent slopes): LR=0.20, p=0.9028 (not supported); providers=5, N=360
