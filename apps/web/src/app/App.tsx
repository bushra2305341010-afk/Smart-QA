import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { BrowserRouter } from "react-router-dom";
import { makeQueryClient } from "./queryClient";
import { ROUTER_FUTURE } from "./routerFuture";
import { AppRoutes } from "./routes";

export function App() {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter future={ROUTER_FUTURE}>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
