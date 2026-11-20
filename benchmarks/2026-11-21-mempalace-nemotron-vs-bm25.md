# MemPalace retrieval benchmark

21 November 2026 · 36 file-navigation queries across three public repositories

The fork's default `groxaxo/Nemotron-3-Embed-1B-AWQ-W4A16@vllm-2048` ran on the RTX 3060 through local vLLM. BM25 used the fork's Okapi scorer with its default parameters of `k1=1.5` and `b=0.75`. Each system searched the same chunks within each repository. [Fork revision](https://github.com/groxaxo/mempalace/commit/888cc20cb0ef280823da4e768acf02252a7c70f7)

## Results

Hit@1 and Hit@5 count how often the expected file appeared at the top or within the first five results. MRR is mean reciprocal rank, with a missed target contributing zero.

| Query group | Nemotron Hit@1 | Nemotron Hit@5 | Nemotron MRR | BM25 Hit@1 | BM25 Hit@5 | BM25 MRR |
|---|---:|---:|---:|---:|---:|---:|
| All queries | 21/36 | 35/36 | 0.736 | 18/36 | 30/36 | 0.650 |
| Exact terms | 13/18 | 18/18 | 0.844 | 12/18 | 18/18 | 0.794 |
| Paraphrases | 8/18 | 17/18 | 0.627 | 6/18 | 12/18 | 0.506 |
| mcp-4k-eyes | 8/12 | 12/12 | 0.794 | 6/12 | 9/12 | 0.612 |
| cozyvoice-fastapi | 4/12 | 11/12 | 0.552 | 4/12 | 10/12 | 0.550 |
| gguf-hf-browser-extractor | 9/12 | 12/12 | 0.861 | 8/12 | 11/12 | 0.788 |

Median query time was 72.5 ms for Nemotron and 5.5 ms for BM25 in this harness. Nemotron time includes the local HTTP embedding request and cosine ranking over precomputed document vectors. BM25 time includes tokenizing and scoring the whole corpus for each query.

## Sample and scoring

I sorted 26 eligible public repositories owned by `groxaxo` by name and used Python's `random.Random(20261121).sample` to select three without replacement. Eligibility required a non-archived source repository with a default branch, a recognized primary programming language, and a reported size from 32 to 6,000 KB. All three sampled repositories had Python as their primary language.

- `mcp-4k-eyes` contributed 15 tracked text files and 194 chunks. [Snapshot](https://github.com/groxaxo/mcp-4k-eyes/tree/d451144ced9a4be02177b1b09b8a71ee36581718)
- `cozyvoice-fastapi` contributed 24 tracked text files and 300 chunks. [Snapshot](https://github.com/groxaxo/cozyvoice-fastapi/tree/8f6cdfaf86b60a4038a7e36dff6dccbea8864bf0)
- `gguf-hf-browser-extractor` contributed 8 tracked text files and 97 chunks. [Snapshot](https://github.com/groxaxo/gguf-hf-browser-extractor/tree/b1a5d6f9e50229ee903da7ef64f1b08ac8663d35)

I labeled 18 file-navigation tasks before scoring, each with an exact-term query and a plain-language paraphrase. MemPalace split the tracked source and documentation at 800 characters with a 100-character overlap and a 50-character minimum. Both systems received the relative path followed by chunk text. Binary assets, the generated `output/` directory, and files over 120,000 bytes were excluded. Each file took the rank of its highest-scoring chunk. The benchmark scored cosine similarity over all chunks with Nemotron and all positive matches with BM25.

This is a small, hand-labeled Python repository sample. It measures whether a search leads to the expected file. An unlisted file may also contain useful information.

## Per-query ranks

### mcp-4k-eyes

| Form | Query | Expected file | Nemotron rank | BM25 rank |
|---|---|---|---:|---:|
| exact | scale_box box_norm width height | `grounding_server.py` | 2 | 2 |
| paraphrase | Which implementation converts a detector rectangle into actual pixel bounds on the image? | `grounding_server.py` | 2 | 3 |
| exact | get_screenshot_base64 screencap /sdcard/screen.png | `agent_phone_control.py` | 1 | 1 |
| paraphrase | Which phone-control example takes a picture of the handset display and encodes it before sending it to the assistant? | `agent_phone_control.py` | 1 | 12 |
| exact | desktop_screenshot.png analyze_screenshot | `agent_desktop_control.py` | 1 | 1 |
| paraphrase | Where is the example that captures the computer display and asks the screenshot analyzer to find UI controls? | `agent_desktop_control.py` | 3 | 8 |
| exact | USB debugging authorization prompt adb devices setup | `ANDROID_SETUP_GUIDE.md` | 1 | 1 |
| paraphrase | Where is the guide for getting a newly connected phone to trust this computer and show up in the device list? | `ANDROID_SETUP_GUIDE.md` | 1 | 1 |
| exact | restore_default_settings window_animation_scale | `adb_utils.py` | 1 | 5 |
| paraphrase | Where is the implementation that puts the handset's visual preferences back after a capture session? | `adb_utils.py` | 5 | 10 |
| exact | parse_ui_hierarchy parse_node xml_content | `adb_utils.py` | 1 | 1 |
| paraphrase | Which utility walks the exported phone control tree and converts it into structured elements? | `adb_utils.py` | 1 | 1 |

### cozyvoice-fastapi

| Form | Query | Expected file | Nemotron rank | BM25 rank |
|---|---|---|---:|---:|
| exact | QUANTIZATION_BITS BitsAndBytes 4-bit 8-bit | `BNB_QUANTIZATION.md` | 2 | 3 |
| paraphrase | Which guide compares the two reduced-precision weight settings and shows how to enable each? | `BNB_QUANTIZATION.md` | 3 | 10 |
| exact | ONNX Models manual HiFi-GAN flow model files | `ONNX_GUIDE.md` | 5 | 2 |
| paraphrase | Where are the graph-runtime model artifacts listed, including where to get them if automatic downloads fail? | `ONNX_GUIDE.md` | 5 | 1 |
| exact | Why TensorRT Underperformed Results Summary | `PERFORMANCE.md` | 2 | 1 |
| paraphrase | Which document reports measured timings and explains why the compiled accelerator path was slower in those trials? | `PERFORMANCE.md` | 7 | 2 |
| exact | encode_audio response_format fmt | `openai_tts_cosyvoice_server.py` | 1 | 1 |
| paraphrase | Where does the server turn a waveform into the final bytes in the requested media format? | `openai_tts_cosyvoice_server.py` | 1 | 2 |
| exact | discover_voice_samples get_voice_file | `openai_tts_cosyvoice_server.py` | 1 | 1 |
| paraphrase | Which implementation discovers usable speaker recordings and maps a requested voice to a local file? | `openai_tts_cosyvoice_server.py` | 1 | 3 |
| exact | setup_tensorrt.sh TensorRT installation script | `setup_tensorrt.sh` | 2 | 4 |
| paraphrase | Which shell installer prepares NVIDIA's compiled inference runtime before the server can use it? | `setup_tensorrt.sh` | 4 | 12 |

### gguf-hf-browser-extractor

| Form | Query | Expected file | Nemotron rank | BM25 rank |
|---|---|---|---:|---:|
| exact | _parse_tensor_info _read_value BytesIO | `extract_gguf_binary.py` | 1 | 1 |
| paraphrase | Which implementation decodes tensor descriptors and typed header values directly from the model file bytes? | `extract_gguf_binary.py` | 1 | 2 |
| exact | Ungroup by layer name SETTLE_TICKS EXPAND_TIMEOUT | `extract.js` | 1 | 1 |
| paraphrase | Where does the browser code open the grouped table and wait for the layer count to stop changing before reading it? | `extract.js` | 1 | 1 |
| exact | _atomic_write _update_index Handler do_POST | `sink_server.py` | 1 | 1 |
| paraphrase | Which server safely replaces saved extraction results and updates the catalog after an upload? | `sink_server.py` | 2 | 1 |
| exact | build_tensor_type_files tensor type output files | `build_tensor_type_files.py` | 1 | 1 |
| paraphrase | Which utility takes existing extraction results and creates separate files organized by tensor storage format? | `build_tensor_type_files.py` | 3 | 8 |
| exact | OpenCode tool bindings SKILL.md | `patches/opencode.md` | 1 | 2 |
| paraphrase | Which integration instructions explain how to register this extractor with the OpenCode agent? | `patches/opencode.md` | 2 | 3 |
| exact | Extraction modes Why browser-first Why local sink | `SKILL.md` | 1 | 1 |
| paraphrase | Where is the overview of the available extraction routes and why the workflow writes to a local receiver? | `SKILL.md` | 1 | 1 |
