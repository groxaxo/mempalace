# Run MemPalace with Nemotron

New configurations on this fork use `nemotron-vllm`. The adapter expects
[`groxaxo/Nemotron-3-Embed-1B-AWQ-W4A16`](https://huggingface.co/groxaxo/Nemotron-3-Embed-1B-AWQ-W4A16)
served through vLLM with at least 4,096 tokens of context. On a compatible GPU
host, follow the checkpoint's vLLM setup and serve it as `nemotron-embed`.
Keep vLLM on `127.0.0.1:8000` when MemPalace runs on the same host.

The adapter sends `passage: ` for indexing and `query: ` for search. It uses
overlapping tokenizer windows for long inputs and stores normalized
2,048-dimensional vectors. Semantic search ranks by vector similarity and
returns up to five matches in the CLI, MCP, and Python API.

## Create a separate palace and check search

```bash
export MEMPALACE_PALACE_PATH="$HOME/.mempalace/palace-nemotron"
export MEMPALACE_EMBEDDING_MODEL=nemotron-vllm
export MEMPALACE_EMBEDDING_API_URL=http://127.0.0.1:8000/v1
export MEMPALACE_EMBEDDING_API_MODEL=nemotron-embed

mempalace mine /path/to/project
mempalace search 'Where are the project settings?' --results 5
```

Set `MEMPALACE_EMBEDDING_API_KEY` in the MemPalace service environment if
vLLM requires authentication. For an existing palace, select its original
embedding model to continue using its index. To convert it to Nemotron,
back it up first, select it explicitly, then run
`mempalace repair rebuild-index --yes` with the Nemotron settings above.

## Share recall across clients

Run a single authenticated HTTP MCP process for the palace on the GPU host.
Set `MEMPALACE_MCP_HTTP_TOKEN` in that process's environment and use the same
palace path and embedding settings as the indexing CLI.

```bash
mempalace serve --host 127.0.0.1 --port 18765
# On each client host that needs a tunnel
ssh -N -L 127.0.0.1:18765:127.0.0.1:18765 user@gpu-host
```

Register `http://127.0.0.1:18765/mcp` as a remote MCP server in Codex,
OpenCode, or Hermes. Configure its `Authorization` header as `Bearer `
followed by the shared token. Run `mempalace_status` and `mempalace_search`
through each client to confirm it reaches the same palace. The fork's
[`develop`](https://github.com/groxaxo/mempalace/tree/develop) branch also
supports forwarding shared Codex Stop and PreCompact checkpoints to the
HTTP writer. That setup needs a client-side hook bridge that stages the
transcript on the writer host.

See the [repository retrieval benchmark](../benchmarks/2026-11-21-mempalace-nemotron-vs-bm25.md)
for the three-repository Nemotron and BM25 comparison and its limitations.
