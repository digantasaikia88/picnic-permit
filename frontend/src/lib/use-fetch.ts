"use client";

import { useCallback, useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";

type State<T> = { data?: T; error?: string; loadedPath?: string };

/**
 * Loads JSON from the API and reloads when the path changes or `reload` is called.
 * The previous data stays on screen while a reload is in progress.
 */
export function useFetch<T>(path: string | null) {
  const [state, setState] = useState<State<T>>({});
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    api<T>(path)
      .then((data) => {
        if (!cancelled) setState({ data, loadedPath: path });
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setState((old) => ({ ...old, error: errorMessage(error), loadedPath: path }));
      });
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);

  return {
    data: state.data,
    error: state.error,
    loading: path !== null && state.loadedPath !== path,
    reload,
  };
}
