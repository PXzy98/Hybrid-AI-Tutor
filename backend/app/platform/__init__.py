"""v4 platform: courses, access, settings and usage (owner Z; docs/design/course-structure.md).

Task Z1 publishes the interfaces with working stand-ins so that other components can build against them:
- `settings.effective_settings` returns the config defaults for any course until Z5 adds the tables;
- `access.require_course_role` denies every request until Z9 provides the course directory;
- `usage` never limits until Z10.
"""
