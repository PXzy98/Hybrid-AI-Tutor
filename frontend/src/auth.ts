import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./api/client";
import { api, type Course, type Me } from "./api/endpoints";

/** The logged-in account, from the server session (GET /auth/me). null = not logged in. */
export function useMe() {
  return useQuery<Me | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.me();
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });
}

/** Clears every cached query (they belong to the previous account). */
export function useResetSession() {
  const qc = useQueryClient();
  return (me: Me | null) => {
    qc.clear();
    qc.setQueryData(["me"], me);
  };
}

/** The courses the caller can see (GET /courses). */
export function useCourses() {
  return useQuery({ queryKey: ["courses"], queryFn: api.courses });
}

export type CourseRole = "instructor" | "student";

/** The caller's role in a course, as the server reports it. An admin without a membership gets the
 * instructor view; what the API refuses stays refused. */
export function roleIn(course: Course, me: Me): CourseRole {
  return course.my_role ?? (me.system_role === "student" ? "student" : "instructor");
}
