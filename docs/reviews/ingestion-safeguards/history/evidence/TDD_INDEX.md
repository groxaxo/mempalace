Every numbered cycle records its actual command, full pytest output, and exit status. A RED run is an expected behavioral failure at that stage; GREEN is the subsequent passing run after the minimal fix. Earlier fixes remain present in later cycles.

| Cycle | RED failure summary | GREEN passing summary |
| --- | --- | --- |
| 01-headerless | [1 failed in 0.04s / EXIT STATUS: 1](tdd/01-headerless-red.txt) | [1 passed in 0.03s / EXIT STATUS: 0](tdd/01-headerless-green.txt) |
| 02-envelope | [7 failed, 9 passed in 0.08s / EXIT STATUS: 1](tdd/02-envelope-red.txt) | [16 passed in 0.04s / EXIT STATUS: 0](tdd/02-envelope-green.txt) |
| 03-encoding | [3 failed, 17 passed in 0.07s / EXIT STATUS: 1](tdd/03-encoding-red.txt) | [20 passed in 0.04s / EXIT STATUS: 0](tdd/03-encoding-green.txt) |
| 04-other-envelopes | [5 failed, 20 passed in 0.09s / EXIT STATUS: 1](tdd/04-other-envelopes-red.txt) | [25 passed in 0.05s / EXIT STATUS: 0](tdd/04-other-envelopes-green.txt) |
| 05-typed-tools | [2 failed, 26 passed in 0.10s / EXIT STATUS: 1](tdd/05-typed-tools-red.txt) | [28 passed in 0.06s / EXIT STATUS: 0](tdd/05-typed-tools-green.txt) |
| 06-tool-limits | [8 failed, 28 passed in 0.15s / EXIT STATUS: 1](tdd/06-tool-limits-red.txt) | [36 passed in 0.07s / EXIT STATUS: 0](tdd/06-tool-limits-green.txt) |
| 07-conversation-gates | [2 failed in 2.20s / EXIT STATUS: 1](tdd/07-conversation-gates-red.txt) | [38 passed in 0.87s / EXIT STATUS: 0](tdd/07-conversation-gates-green.txt) |
| 08-project | [2 failed, 3 passed in 0.84s / EXIT STATUS: 1](tdd/08-project-red.txt) | [41 passed in 0.81s / EXIT STATUS: 0](tdd/08-project-green.txt) |
| 09-live-manual | [3 failed, 5 passed in 0.84s / EXIT STATUS: 1](tdd/09-live-manual-red.txt) | [44 passed in 0.86s / EXIT STATUS: 0](tdd/09-live-manual-green.txt) |
| 10-prechunk-source | [2 failed, 44 passed in 0.93s / EXIT STATUS: 1](tdd/10-prechunk-source-red.txt) | [46 passed in 0.75s / EXIT STATUS: 0](tdd/10-prechunk-source-green.txt) |
| 11-mcp | [6 failed in 0.87s / EXIT STATUS: 1](tdd/11-mcp-red.txt) | [52 passed in 0.86s / EXIT STATUS: 0](tdd/11-mcp-green.txt) |
| 12-structure | [4 failed, 39 passed in 0.15s / EXIT STATUS: 1](tdd/12-structure-red.txt) | [58 passed in 1.55s / EXIT STATUS: 0](tdd/12-structure-green.txt) |
| 13-shadow | [2 failed in 0.15s / EXIT STATUS: 1](tdd/13-shadow-red.txt) | [60 passed in 1.61s / EXIT STATUS: 0](tdd/13-shadow-green.txt) |
| 14-refusal-boundaries | [5 failed, 43 passed in 0.26s / EXIT STATUS: 1](tdd/14-refusal-boundaries-red.txt) | [65 passed in 1.00s / EXIT STATUS: 0](tdd/14-refusal-boundaries-green.txt) |
| 15-source-context | [2 failed, 66 passed in 1.12s / EXIT STATUS: 1](tdd/15-source-context-red.txt) | [68 passed in 1.02s / EXIT STATUS: 0](tdd/15-source-context-green.txt) |
| 16-media-fields | [4 failed, 49 passed in 0.22s / EXIT STATUS: 1](tdd/16-media-fields-red.txt) | [72 passed in 1.22s / EXIT STATUS: 0](tdd/16-media-fields-green.txt) |
| 17-marker-fragments | [1 failed in 0.08s / EXIT STATUS: 1](tdd/17-marker-fragments-red.txt) | [79 passed in 1.55s / EXIT STATUS: 0](tdd/17-marker-fragments-green.txt) |
| 18-session-families | [3 failed, 56 passed in 0.18s / EXIT STATUS: 1](tdd/18-session-families-red.txt) | [84 passed in 1.00s / EXIT STATUS: 0](tdd/18-session-families-green.txt) |

The corrected cycle-12 RED run is also retained as `12-structure-red-corrected.txt`. Marker-boundary probes passed before a different boundary fixture reproduced the cycle-17 failure; their passing outputs are retained outside `tdd`. The positive/preservation expansion first exposed a storage-spy bug (`ids=None`) and then passed after correcting the spy; both outputs are retained. Those fixture/probe runs are not represented as deployed-source failures.
