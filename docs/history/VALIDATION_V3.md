# Validation of the complete integration

- Backend: **442 passed, 1 external-provider test deselected**.
- Frontend: **14 tests passed**; TypeScript and Vite production build passed.
- Main's complete instructor dashboard suite is present, including account permissions, class summaries,
  privacy-safe logs, uploads, runtime settings, config history and startup restoration.
- Existing RAG tests and semantic-policy/evidence/SSE tests pass together. Added integrated coverage
  exercises all instructor APIs after a semantic+real-RAG student request, and confirms upload storage
  versus the current lack of an ingestion hook.
- First-run helper tests cover dotenv quoting, valid initial passwords, short/matching/injected-password
  rejection, preserving existing .env and retrying invalid input.
- Actual-model smoke: 8 prompts x LR/SVM with local MiniLM, unchanged 500-question weights,
  medical_hybrid and both evidence cross-encoders. See eval/results/semantic_rag_smoke.json.
- Browser: all five instructor tabs load; student creation, upload status, request logs and progress-display
  setting work. Student live progress precedes the answer; LR/SVM choice and display-off work.
  Student and teacher layouts have no horizontal overflow at 390px. No page errors were observed.
- Answer generation in the browser/API integration tests uses test doubles. Actual Ollama or paid Cloud
  answer quality was not evaluated. Setup/source tests ran in Linux; PowerShell launchers are supplied
  for Windows and were not executed on the user's computer.

Real-model observations are not reported as accuracy: the pressure and migraine course prompts pass
evidence checks and stay Local; a complex case goes Cloud before retrieval; freshness-dependent queries
reject unverified-current snapshots. Some asthma/pneumonia prompts are falsely rejected by current
thresholds; one diabetes source request is missed by the evidence-need classifier.
