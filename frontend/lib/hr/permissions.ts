/**
 * Frontend mirror of the backend permission catalogue
 * (app/auth/permissions.py).
 *
 * These constants are the source of truth for *frontend* checks —
 * navigation filtering, button gating, route guards. The backend
 * re-validates every action, so a malicious user editing localStorage
 * to add fake permissions still gets 403 from the API; the constants
 * here are purely for UX (don't show a button if the click will 403).
 *
 * Keep this file in lockstep with backend/app/auth/permissions.py — if
 * a key is renamed or added on the backend, mirror it here.
 */

// Dashboard
export const PERM_HR_DASHBOARD_VIEW = "hr:dashboard:view";

// Jobs
export const PERM_HR_JOBS_VIEW = "hr:jobs:view";
export const PERM_HR_JOBS_VIEW_DEPT = "hr:jobs:view_dept";
export const PERM_HR_JOBS_CREATE = "hr:jobs:create";
export const PERM_HR_JOBS_EDIT = "hr:jobs:edit";
export const PERM_HR_JOBS_APPROVE = "hr:jobs:approve";
export const PERM_HR_JOBS_PUBLISH = "hr:jobs:publish";
export const PERM_HR_JOBS_DELETE = "hr:jobs:delete";

// Candidates
export const PERM_HR_CANDIDATES_VIEW_LIST = "hr:candidates:view_list";
export const PERM_HR_CANDIDATES_VIEW_FULL = "hr:candidates:view_full";
export const PERM_HR_CANDIDATES_VIEW_DEPT = "hr:candidates:view_dept";
export const PERM_HR_CANDIDATES_EDIT = "hr:candidates:edit";
export const PERM_HR_CANDIDATES_STATUS_UPDATE = "hr:candidates:status_update";
export const PERM_HR_CANDIDATES_STATUS_OVERRIDE = "hr:candidates:status_override";
export const PERM_HR_CANDIDATES_DELETE = "hr:candidates:delete";
export const PERM_HR_CANDIDATES_SCORE_OVERRIDE = "hr:candidates:score_override";
export const PERM_HR_CANDIDATES_BLACKLIST = "hr:candidates:blacklist";

// Interviews
export const PERM_HR_INTERVIEWS_VIEW_ALL = "hr:interviews:view_all";
export const PERM_HR_INTERVIEWS_VIEW_MINE = "hr:interviews:view_mine";
export const PERM_HR_INTERVIEWS_SCHEDULE = "hr:interviews:schedule";
export const PERM_HR_INTERVIEWS_RESCHEDULE = "hr:interviews:reschedule";
export const PERM_HR_INTERVIEWS_FEEDBACK = "hr:interviews:feedback";
export const PERM_HR_INTERVIEWS_DELETE = "hr:interviews:delete";

// Offers
export const PERM_HR_OFFERS_VIEW = "hr:offers:view";
export const PERM_HR_OFFERS_CREATE = "hr:offers:create";
export const PERM_HR_OFFERS_APPROVE = "hr:offers:approve";
export const PERM_HR_OFFERS_DELETE = "hr:offers:delete";

// Reports + exports
export const PERM_HR_REPORTS_VIEW_ALL = "hr:reports:view_all";
export const PERM_HR_REPORTS_VIEW_DEPT = "hr:reports:view_dept";
export const PERM_HR_REPORTS_VIEW_MINE = "hr:reports:view_mine";
export const PERM_HR_REPORTS_EXPORT = "hr:reports:export";
export const PERM_HR_CV_DOWNLOAD = "hr:cv:download";

// Settings + admin
export const PERM_HR_SETTINGS_MANAGE = "hr:settings:manage";
export const PERM_HR_AUDIT_READ = "hr:audit:read";
export const PERM_HR_USERS_MANAGE = "hr:users:manage";


/**
 * Convenience: any of the three "view interviews" permissions counts as
 * "can see the Interviews tab".
 */
export const ANY_INTERVIEW_VIEW = [
  PERM_HR_INTERVIEWS_VIEW_ALL,
  PERM_HR_INTERVIEWS_VIEW_MINE,
] as const;

export const ANY_REPORT_VIEW = [
  PERM_HR_REPORTS_VIEW_ALL,
  PERM_HR_REPORTS_VIEW_DEPT,
  PERM_HR_REPORTS_VIEW_MINE,
] as const;

export const ANY_JOB_VIEW = [
  PERM_HR_JOBS_VIEW,
  PERM_HR_JOBS_VIEW_DEPT,
] as const;

export const ANY_CANDIDATE_VIEW = [
  PERM_HR_CANDIDATES_VIEW_LIST,
  PERM_HR_CANDIDATES_VIEW_DEPT,
] as const;
