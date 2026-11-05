# S9 — Learning plan and visibility transitions (offline core)

Updated in `backend/app/learner/learning_plan.py`. The helper enforces:
- Mode A offers no individual view; switching to B requires explicit student acknowledgement.
- Opting out clears visible_since. Re-opt-in creates a new consent epoch, not retroactive visibility.
- Learning plans must match course and student, use only known KCs, have bounded notes,
  and be created after consent and a successful audit callback.
- No persistence or student data is used in tests.

Z4/Z10 must enforce instructor role, student consent and persistent audit within a
safe transaction, and expose v2 endpoints. This core is not permission enforcement,
and is not a complete S9 deployment.
