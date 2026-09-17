# Baseline Benchmarks

Local benchmark using the deterministic mock provider.

Configuration:

- 20 requests per run
- mock upstream delay: 1000 ms
- client concurrency matched `MAX_IN_FLIGHT`
- local proxy and mock provider on the same VM

| MAX_IN_FLIGHT | Successful req/s | Success rate | p50 ms | p95 ms | p99 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.98 | 100% | 1013.6 | 1023.3 | 1049.7 |
| 2 | 1.96 | 100% | 1016.0 | 1036.0 | 1058.6 |
| 4 | 3.88 | 100% | 1020.9 | 1053.4 | 1077.7 |

## Observation

With the mock provider, successful throughput scales almost linearly
with the concurrency limit while successful-request latency remains
close to the configured 1000 ms upstream delay.

This benchmark validates the proxy's asynchronous request path and
bounded-concurrency mechanism. It does not establish the optimal
production concurrency limit for a real LLM provider.

## Streaming TTFT Baseline

Local end-to-end streaming measurements through the proxy.

Configuration:

- mock chunk delay: 300 ms
- message: `hello streaming world`
- five text chunks plus one final completion chunk
- proxy and mock provider running on the same VM

| Mock first-chunk delay | Measured TTFT | TTFT difference | Measured total time |
|---:|---:|---:|---:|
| 500 ms | 579.2 ms | +79.2 ms | 1795.2 ms |
| 1000 ms | 1080.6 ms | +80.6 ms | 2289.5 ms |
| 2000 ms | 2085.4 ms | +85.4 ms | 3290.8 ms |

### Observation

The measured time to first streamed data event follows the configured
upstream first-chunk delay closely. In these local runs, the additional
end-to-end delay remained roughly constant as the upstream delay grew.

These measurements include client, HTTP, proxy, mock-provider, and
event-loop overhead. They should not be interpreted as an isolated
measurement of proxy-only overhead.
