import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "./api/client";
import { api, type Me } from "./api/endpoints";

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

export function homeFor(me: Me): string {
  if (me.must_change_password) return "/change-password";
  return me.role === "instructor" ? "/admin" : "/chat";
}
