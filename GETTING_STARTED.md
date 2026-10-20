# Fully integrated version v3

English version of [开始使用.md](开始使用.md). Two statements were updated on 19 Oct 2026 to match the current
code; they are marked *(updated)*.

This project combines: the full instructor dashboard from the main branch, Siyun's real medical RAG, and our
semantic routing. The original three classification labels, the evidence check, the LR/SVM weights trained on
500 questions, the student progress panel and the instructor switches are all kept.

## 1. Put it in a new folder

Suggested location: `D:\Documents\Courses\ELG5902\Hybrid-AI-Tutor-integrated-v3`.
Check that this folder directly contains `config.yaml`, `backend`, `frontend` and `setup_local.py`.
The root of this ZIP package is the project root.

Keep the old folder; there is no need to delete existing virtual environments. Do not copy the old
backend/frontend code into the new folder.
To keep the existing accounts, stop the old backend first, then copy the old `.env` and `data/app.db` to the
same places in the new folder.
If the old `.env` has a `DATABASE_URL` pointing to an external database, that path still applies.

## 2. First installation

In PowerShell, go to the new project folder and run:

```powershell
cd "D:\Documents\Courses\ELG5902\Hybrid-AI-Tutor-integrated-v3"
& "D:\Softwares\python312\python.exe" .\setup_local.py
```

The script creates this project's `.venv`, installs the dependencies, checks the spaCy model that the actual
configuration requires, reuses or prepares the semantic models, verifies that the backend starts, and installs
and builds the frontend. An existing `.env` and database are kept.
Without a `.env`, it asks for the instructor username, an initial password of at least 10 characters, and the
Ollama model name. The password is not shown while you type.
The default Ollama address is this machine, and the default model is the one you used before,
`qwen3.5:9b-q4_K_M`.
Keep the Ollama application running; if you already have this model, there is no need to download it again.

To reuse the virtual environment you just installed, run instead:

```powershell
$pythonExe = "D:\Documents\Courses\ELG5902\project file\Hybrid-AI-Tutor-semantic-routing-tongkai\Hybrid-AI-Tutor-semantic-routing-tongkai\.venv\Scripts\python.exe"
& $pythonExe .\setup_local.py --reuse-python "$pythonExe"
```

The weights for the 500 questions are included. The base semantic model cache is reused if it is still there;
Qwen is not retrained.
The spaCy model the script reads matches the configuration, which avoids installing `lg` while the runtime asks
for `sm`.
The cloud key and model can be filled in `.env` later. *(updated)* If they are empty, a question routed to the
cloud is answered by the local model, and the student sees why ("No cloud model is connected…").

## 3. Start the backend and frontend

First PowerShell window, in the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_backend.ps1
```

If you chose to reuse the old virtual environment, use instead:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_backend.ps1 -PythonPath "D:\Documents\Courses\ELG5902\project file\Hybrid-AI-Tutor-semantic-routing-tongkai\Hybrid-AI-Tutor-semantic-routing-tongkai\.venv\Scripts\python.exe"
```

Second PowerShell window, also in the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_frontend.ps1
```

Open http://127.0.0.1:5173. At the first login the instructor must change the initial password.
*(updated)* The instructor dashboard has six pages: Students, Class summary, Settings, Logs, Content and
Feedback.
You can create student accounts directly on the Students page; Settings can switch the routing progress display
for students on or off.

## 4. Git branch

This package contains a restorable local branch `integration/main-rag-semantic` that keeps the commit history of
the three source branches. In the project root, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\restore_git.ps1
git status
```

This restores `.git` and the local integration branch, and keeps the current files, configuration and database.
Nothing is uploaded or merged automatically.
After testing, run:

```powershell
git push -u origin integration/main-rag-semantic
```

If you change source code later, review the changes first, then commit and push. `.env`, the database, virtual
environments and caches are not uploaded.
Do not run the previous version's `apply_test_push_routing.py` again; it was for the old patch paths.

## 5. Validation and scope

See `docs/INTEGRATION.md` and `docs/VALIDATION_V3.md`.
With the material-sync patch installed, the instructor dashboard shows built-in materials and uploaded materials
separately, with their retrieval status.
Uploaded files are added automatically to the retrieval for their topic, and are loaded again after a restart;
materials uploaded earlier do not need to be uploaded again.
Supported: TXT, Markdown, HTML, DOCX, and PDF with a text layer; scanned PDFs need OCR first.
Details: `docs/MATERIALS_SYNC.md`.
The semantic evidence judgement still makes mistakes; the 500 questions carry prototype policy labels and do not
yet represent an assessment of the actual Qwen capability.
This package contains no real passwords, API keys, database, virtual environments, `node_modules` or downloaded
base models.
