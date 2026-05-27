"""Fine-grained HR permission catalogue (Phase 1 — RBAC overhaul).

Every HR endpoint now gates on a permission key from this module instead
of the coarse ``SCOPE_HR`` check. The catalogue defines:

1. **Permission key constants** — every sensitive HR action has a key.
2. **Role-to-permission matrix** — the seven standard HR roles and the
   keys each one grants by default.

The roles are seeded via :mod:`app.scripts.seed_users` and via the
Alembic migration ``20260527_0001_hr_rbac_permissions``. Existing
installations keep their users; the migration just bolts the new
permissions onto whichever role they already have.

Naming convention
-----------------
Keys follow ``hr:<area>:<verb>`` so they sort nicely in any admin UI
and make their intent obvious. Verbs:

- ``view``      — read access (the default safe verb)
- ``view_all``  — see everyone's data (overrides any "mine"/"dept" gate)
- ``view_dept`` — see data scoped to user.department
- ``view_mine`` — see only data assigned to / created by the user
- ``create``    — make new rows
- ``edit``      — update existing rows
- ``delete``    — hard-delete or archive
- ``approve``   — sign off (job/offer)
- ``publish``   — make publicly visible
- ``override``  — manager-only escape hatches
- ``export``    — download data outside the app
- ``manage``    — settings / config / role assignments
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from app.models.auth import SCOPE_HR


# ---------------------------------------------------------------------------
# Permission key constants
# ---------------------------------------------------------------------------

# Dashboard ----------------------------------------------------------------
PERM_HR_DASHBOARD_VIEW = "hr:dashboard:view"

# Jobs ---------------------------------------------------------------------
PERM_HR_JOBS_VIEW = "hr:jobs:view"
PERM_HR_JOBS_VIEW_DEPT = "hr:jobs:view_dept"
PERM_HR_JOBS_CREATE = "hr:jobs:create"
PERM_HR_JOBS_EDIT = "hr:jobs:edit"
PERM_HR_JOBS_APPROVE = "hr:jobs:approve"
PERM_HR_JOBS_PUBLISH = "hr:jobs:publish"
PERM_HR_JOBS_DELETE = "hr:jobs:delete"

# Candidates ---------------------------------------------------------------
PERM_HR_CANDIDATES_VIEW_LIST = "hr:candidates:view_list"
PERM_HR_CANDIDATES_VIEW_FULL = "hr:candidates:view_full"
PERM_HR_CANDIDATES_VIEW_DEPT = "hr:candidates:view_dept"
PERM_HR_CANDIDATES_EDIT = "hr:candidates:edit"
PERM_HR_CANDIDATES_STATUS_UPDATE = "hr:candidates:status_update"
PERM_HR_CANDIDATES_STATUS_OVERRIDE = "hr:candidates:status_override"
PERM_HR_CANDIDATES_DELETE = "hr:candidates:delete"
PERM_HR_CANDIDATES_SCORE_OVERRIDE = "hr:candidates:score_override"
PERM_HR_CANDIDATES_BLACKLIST = "hr:candidates:blacklist"

# Interviews ---------------------------------------------------------------
PERM_HR_INTERVIEWS_VIEW_ALL = "hr:interviews:view_all"
PERM_HR_INTERVIEWS_VIEW_MINE = "hr:interviews:view_mine"
PERM_HR_INTERVIEWS_SCHEDULE = "hr:interviews:schedule"
PERM_HR_INTERVIEWS_RESCHEDULE = "hr:interviews:reschedule"
PERM_HR_INTERVIEWS_FEEDBACK = "hr:interviews:feedback"
PERM_HR_INTERVIEWS_DELETE = "hr:interviews:delete"

# Offers -------------------------------------------------------------------
PERM_HR_OFFERS_VIEW = "hr:offers:view"
PERM_HR_OFFERS_CREATE = "hr:offers:create"
PERM_HR_OFFERS_APPROVE = "hr:offers:approve"
PERM_HR_OFFERS_DELETE = "hr:offers:delete"

# Reports + exports --------------------------------------------------------
PERM_HR_REPORTS_VIEW_ALL = "hr:reports:view_all"
PERM_HR_REPORTS_VIEW_DEPT = "hr:reports:view_dept"
PERM_HR_REPORTS_VIEW_MINE = "hr:reports:view_mine"
PERM_HR_REPORTS_EXPORT = "hr:reports:export"
PERM_HR_CV_DOWNLOAD = "hr:cv:download"

# Settings + admin ---------------------------------------------------------
PERM_HR_SETTINGS_MANAGE = "hr:settings:manage"
PERM_HR_AUDIT_READ = "hr:audit:read"
PERM_HR_USERS_MANAGE = "hr:users:manage"  # super admin only


# ---------------------------------------------------------------------------
# Permission descriptors — keep in lockstep with the constants above
# ---------------------------------------------------------------------------

# (key, description) — every key MUST appear here, the migration uses this
# tuple to seed the ``permissions`` table.
HR_PERMISSIONS: Tuple[Tuple[str, str], ...] = (
    (PERM_HR_DASHBOARD_VIEW, "View HR dashboard"),
    # Jobs
    (PERM_HR_JOBS_VIEW, "View all job openings"),
    (PERM_HR_JOBS_VIEW_DEPT, "View jobs in own department"),
    (PERM_HR_JOBS_CREATE, "Create new job openings"),
    (PERM_HR_JOBS_EDIT, "Edit job openings"),
    (PERM_HR_JOBS_APPROVE, "Approve, reject or request revision on submitted jobs"),
    (PERM_HR_JOBS_PUBLISH, "Publish / unpublish approved jobs"),
    (PERM_HR_JOBS_DELETE, "Delete job openings"),
    # Candidates
    (PERM_HR_CANDIDATES_VIEW_LIST, "View candidates list (search / filter)"),
    (PERM_HR_CANDIDATES_VIEW_FULL, "View candidate full profile + CV + history"),
    (PERM_HR_CANDIDATES_VIEW_DEPT, "View candidates in own department"),
    (PERM_HR_CANDIDATES_EDIT, "Edit candidate profile, parse CV, override score"),
    (PERM_HR_CANDIDATES_STATUS_UPDATE, "Change candidate workflow status"),
    (
        PERM_HR_CANDIDATES_STATUS_OVERRIDE,
        "Override transitions normally blocked by workflow rules (manager only)",
    ),
    (PERM_HR_CANDIDATES_DELETE, "Delete / archive candidate records"),
    (PERM_HR_CANDIDATES_SCORE_OVERRIDE, "Override candidate scores"),
    (PERM_HR_CANDIDATES_BLACKLIST, "Blacklist candidates"),
    # Interviews
    (PERM_HR_INTERVIEWS_VIEW_ALL, "View every interview in the system"),
    (PERM_HR_INTERVIEWS_VIEW_MINE, "View only own interviews"),
    (PERM_HR_INTERVIEWS_SCHEDULE, "Schedule new interviews"),
    (PERM_HR_INTERVIEWS_RESCHEDULE, "Edit / reschedule existing interviews"),
    (PERM_HR_INTERVIEWS_FEEDBACK, "Submit interview feedback"),
    (PERM_HR_INTERVIEWS_DELETE, "Delete interview rows"),
    # Offers
    (PERM_HR_OFFERS_VIEW, "View offers"),
    (PERM_HR_OFFERS_CREATE, "Prepare / edit offer letters"),
    (PERM_HR_OFFERS_APPROVE, "Approve and issue offers to candidates"),
    (PERM_HR_OFFERS_DELETE, "Delete / withdraw offers"),
    # Reports
    (PERM_HR_REPORTS_VIEW_ALL, "View all HR reports"),
    (PERM_HR_REPORTS_VIEW_DEPT, "View reports scoped to own department"),
    (PERM_HR_REPORTS_VIEW_MINE, "View reports scoped to own interviews"),
    (PERM_HR_REPORTS_EXPORT, "Export HR reports as Excel/CSV/PDF"),
    (PERM_HR_CV_DOWNLOAD, "Download candidate CV files"),
    # Settings
    (PERM_HR_SETTINGS_MANAGE, "Manage HR settings, auto-review rules, templates"),
    (PERM_HR_AUDIT_READ, "View HR audit log"),
    (PERM_HR_USERS_MANAGE, "Manage HR users and assign roles"),
)


# Index for quick lookup
HR_PERMISSION_KEYS = frozenset(key for key, _ in HR_PERMISSIONS)


# ---------------------------------------------------------------------------
# Role-to-permission matrix (the user's chosen "Standard ATS defaults")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleSpec:
    name: str
    description: str
    permissions: Tuple[str, ...] = field(default_factory=tuple)


# Helper: full HR set for the all-powerful roles
_ALL_HR = tuple(key for key, _ in HR_PERMISSIONS)

ROLE_SUPER_ADMIN = "Super Admin"
ROLE_HR_ADMIN = "HR Admin"
ROLE_HR_MANAGER = "HR Manager"
ROLE_HR_EXECUTIVE = "HR Executive"
ROLE_DEPT_MANAGER = "Department Manager"
ROLE_INTERVIEWER = "Interviewer"
ROLE_VIEWER = "Viewer / Auditor"


HR_ROLES: Tuple[RoleSpec, ...] = (
    # Super Admin gets every key explicitly (and bypasses checks via
    # is_superuser anyway, but the explicit grant makes audit cleaner).
    RoleSpec(
        name=ROLE_SUPER_ADMIN,
        description="Full system access — manages roles and permissions.",
        permissions=_ALL_HR + (PERM_HR_USERS_MANAGE,),
    ),
    # HR Admin — runs day-to-day HR operations but cannot approve jobs/offers
    # and cannot delete records (those need a Manager).
    RoleSpec(
        name=ROLE_HR_ADMIN,
        description=(
            "Day-to-day HR operations. Creates and edits jobs (draft/submit), "
            "manages candidates, schedules interviews, prepares offers. "
            "Cannot approve jobs or offers, cannot delete records."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_JOBS_VIEW,
            PERM_HR_JOBS_CREATE,
            PERM_HR_JOBS_EDIT,
            PERM_HR_CANDIDATES_VIEW_LIST,
            PERM_HR_CANDIDATES_VIEW_FULL,
            PERM_HR_CANDIDATES_EDIT,
            PERM_HR_CANDIDATES_STATUS_UPDATE,
            PERM_HR_CANDIDATES_SCORE_OVERRIDE,
            PERM_HR_INTERVIEWS_VIEW_ALL,
            PERM_HR_INTERVIEWS_VIEW_MINE,
            PERM_HR_INTERVIEWS_SCHEDULE,
            PERM_HR_INTERVIEWS_RESCHEDULE,
            PERM_HR_INTERVIEWS_FEEDBACK,
            PERM_HR_OFFERS_VIEW,
            PERM_HR_OFFERS_CREATE,
            PERM_HR_REPORTS_VIEW_ALL,
            PERM_HR_REPORTS_EXPORT,
            PERM_HR_CV_DOWNLOAD,
            PERM_HR_SETTINGS_MANAGE,
            PERM_HR_AUDIT_READ,
        ),
    ),
    # HR Manager — approval + delete authority on top of everything HR Admin does.
    RoleSpec(
        name=ROLE_HR_MANAGER,
        description=(
            "Senior HR with approval authority: approves/rejects job openings "
            "and offers, can override candidate workflow status, can delete or "
            "blacklist."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_JOBS_VIEW,
            PERM_HR_JOBS_CREATE,
            PERM_HR_JOBS_EDIT,
            PERM_HR_JOBS_APPROVE,
            PERM_HR_JOBS_PUBLISH,
            PERM_HR_JOBS_DELETE,
            PERM_HR_CANDIDATES_VIEW_LIST,
            PERM_HR_CANDIDATES_VIEW_FULL,
            PERM_HR_CANDIDATES_EDIT,
            PERM_HR_CANDIDATES_STATUS_UPDATE,
            PERM_HR_CANDIDATES_STATUS_OVERRIDE,
            PERM_HR_CANDIDATES_SCORE_OVERRIDE,
            PERM_HR_CANDIDATES_BLACKLIST,
            PERM_HR_CANDIDATES_DELETE,
            PERM_HR_INTERVIEWS_VIEW_ALL,
            PERM_HR_INTERVIEWS_VIEW_MINE,
            PERM_HR_INTERVIEWS_SCHEDULE,
            PERM_HR_INTERVIEWS_RESCHEDULE,
            PERM_HR_INTERVIEWS_FEEDBACK,
            PERM_HR_INTERVIEWS_DELETE,
            PERM_HR_OFFERS_VIEW,
            PERM_HR_OFFERS_CREATE,
            PERM_HR_OFFERS_APPROVE,
            PERM_HR_OFFERS_DELETE,
            PERM_HR_REPORTS_VIEW_ALL,
            PERM_HR_REPORTS_EXPORT,
            PERM_HR_CV_DOWNLOAD,
            PERM_HR_SETTINGS_MANAGE,
            PERM_HR_AUDIT_READ,
        ),
    ),
    # HR Executive / Recruiter — creates drafts, manages assigned candidates.
    # Cannot approve jobs or offers, cannot delete approved records, cannot
    # approve their own submissions (enforced row-level in endpoint code).
    RoleSpec(
        name=ROLE_HR_EXECUTIVE,
        description=(
            "Recruiter: creates job drafts, manages candidates, schedules "
            "interviews. Cannot approve, cannot delete, cannot approve own "
            "submissions."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_JOBS_VIEW,
            PERM_HR_JOBS_CREATE,
            PERM_HR_JOBS_EDIT,
            PERM_HR_CANDIDATES_VIEW_LIST,
            PERM_HR_CANDIDATES_VIEW_FULL,
            PERM_HR_CANDIDATES_EDIT,
            PERM_HR_CANDIDATES_STATUS_UPDATE,
            PERM_HR_INTERVIEWS_VIEW_ALL,
            PERM_HR_INTERVIEWS_VIEW_MINE,
            PERM_HR_INTERVIEWS_SCHEDULE,
            PERM_HR_INTERVIEWS_RESCHEDULE,
            PERM_HR_INTERVIEWS_FEEDBACK,
            PERM_HR_OFFERS_VIEW,
            PERM_HR_REPORTS_VIEW_ALL,
            PERM_HR_REPORTS_EXPORT,
            PERM_HR_CV_DOWNLOAD,
        ),
    ),
    # Department Manager — read access scoped to their department (filtering
    # happens in endpoint code via user.department; this role has the
    # *_dept permissions only).
    RoleSpec(
        name=ROLE_DEPT_MANAGER,
        description=(
            "Reviews shortlisted candidates and interview reports for own "
            "department. Can recommend but not change final status."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_JOBS_VIEW_DEPT,
            PERM_HR_CANDIDATES_VIEW_DEPT,
            PERM_HR_INTERVIEWS_VIEW_ALL,  # filtered to dept rows in endpoint
            PERM_HR_INTERVIEWS_FEEDBACK,
            PERM_HR_REPORTS_VIEW_DEPT,
            PERM_HR_REPORTS_EXPORT,
            PERM_HR_CV_DOWNLOAD,
        ),
    ),
    # Interviewer — sees only assigned interviews + interview-related screens.
    # No candidate list, no offers, no settings.
    RoleSpec(
        name=ROLE_INTERVIEWER,
        description=(
            "Sees only assigned interviews. Submits feedback. Cannot browse "
            "candidates, jobs, offers, or HR settings."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_INTERVIEWS_VIEW_MINE,
            PERM_HR_INTERVIEWS_FEEDBACK,
            PERM_HR_REPORTS_VIEW_MINE,
        ),
    ),
    # Viewer / Auditor — read-only across all reports for audit / compliance.
    RoleSpec(
        name=ROLE_VIEWER,
        description=(
            "Read-only: all reports plus the HR audit log. No write access "
            "anywhere."
        ),
        permissions=(
            PERM_HR_DASHBOARD_VIEW,
            PERM_HR_JOBS_VIEW,
            PERM_HR_CANDIDATES_VIEW_LIST,
            PERM_HR_CANDIDATES_VIEW_FULL,
            PERM_HR_INTERVIEWS_VIEW_ALL,
            PERM_HR_OFFERS_VIEW,
            PERM_HR_REPORTS_VIEW_ALL,
            PERM_HR_REPORTS_EXPORT,
            PERM_HR_CV_DOWNLOAD,
            PERM_HR_AUDIT_READ,
        ),
    ),
)


# Index for quick lookup by name
HR_ROLES_BY_NAME = {spec.name: spec for spec in HR_ROLES}


__all__ = [
    # constants
    "PERM_HR_DASHBOARD_VIEW",
    "PERM_HR_JOBS_VIEW",
    "PERM_HR_JOBS_VIEW_DEPT",
    "PERM_HR_JOBS_CREATE",
    "PERM_HR_JOBS_EDIT",
    "PERM_HR_JOBS_APPROVE",
    "PERM_HR_JOBS_PUBLISH",
    "PERM_HR_JOBS_DELETE",
    "PERM_HR_CANDIDATES_VIEW_LIST",
    "PERM_HR_CANDIDATES_VIEW_FULL",
    "PERM_HR_CANDIDATES_VIEW_DEPT",
    "PERM_HR_CANDIDATES_EDIT",
    "PERM_HR_CANDIDATES_STATUS_UPDATE",
    "PERM_HR_CANDIDATES_STATUS_OVERRIDE",
    "PERM_HR_CANDIDATES_DELETE",
    "PERM_HR_CANDIDATES_SCORE_OVERRIDE",
    "PERM_HR_CANDIDATES_BLACKLIST",
    "PERM_HR_INTERVIEWS_VIEW_ALL",
    "PERM_HR_INTERVIEWS_VIEW_MINE",
    "PERM_HR_INTERVIEWS_SCHEDULE",
    "PERM_HR_INTERVIEWS_RESCHEDULE",
    "PERM_HR_INTERVIEWS_FEEDBACK",
    "PERM_HR_INTERVIEWS_DELETE",
    "PERM_HR_OFFERS_VIEW",
    "PERM_HR_OFFERS_CREATE",
    "PERM_HR_OFFERS_APPROVE",
    "PERM_HR_OFFERS_DELETE",
    "PERM_HR_REPORTS_VIEW_ALL",
    "PERM_HR_REPORTS_VIEW_DEPT",
    "PERM_HR_REPORTS_VIEW_MINE",
    "PERM_HR_REPORTS_EXPORT",
    "PERM_HR_CV_DOWNLOAD",
    "PERM_HR_SETTINGS_MANAGE",
    "PERM_HR_AUDIT_READ",
    "PERM_HR_USERS_MANAGE",
    # roles
    "ROLE_SUPER_ADMIN",
    "ROLE_HR_ADMIN",
    "ROLE_HR_MANAGER",
    "ROLE_HR_EXECUTIVE",
    "ROLE_DEPT_MANAGER",
    "ROLE_INTERVIEWER",
    "ROLE_VIEWER",
    # collections
    "HR_PERMISSIONS",
    "HR_PERMISSION_KEYS",
    "HR_ROLES",
    "HR_ROLES_BY_NAME",
    "RoleSpec",
    # re-exported for migrations
    "SCOPE_HR",
]
