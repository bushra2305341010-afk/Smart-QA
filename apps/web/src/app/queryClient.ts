import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";

/** Client errors (4xx) are answers, not glitches: do not retry them. */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
        staleTime: 5_000,
      },
      mutations: { retry: false },
    },
  });
}
