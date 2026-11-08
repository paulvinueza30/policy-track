"use client";
// Who the signed-in user follows, shared by every follow control on a page.
import { useEffect, useSyncExternalStore } from "react";
import { ApiError, sessionRequest } from "@/lib/api";

export const FOLLOW_LIMIT = 20;
export const FOLLOW_LIMIT_MESSAGE = `You can follow up to ${FOLLOW_LIMIT} lawmakers. Unfollow someone to add another.`;

const SERVER_STATE = { status: "idle", following: [], user: null };
let state = SERVER_STATE;
let loading = null;
const listeners = new Set();

function publish(next) {
  state = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function load() {
  if (state.status !== "idle") return loading;
  publish({ ...state, status: "loading" });
  loading = sessionRequest("me")
    .then((user) => publish({ status: "ready", following: user.preferences?.following ?? [], user }))
    .catch((error) => publish({ ...SERVER_STATE, status: error.status === 401 ? "signedOut" : "error" }));
  return loading;
}

/** Call after signing in or out, so the next control asks the server again. */
export function resetFollowing() {
  loading = null;
  publish(SERVER_STATE);
}

/** Keep controls current when the following list changes somewhere else, such as the feed page. */
export function syncFollowing(following) {
  if (state.status === "ready") publish({ ...state, following });
}

export async function setFollowed(bioguideId, follow) {
  if (follow && state.following.length >= FOLLOW_LIMIT) throw new ApiError(422, FOLLOW_LIMIT_MESSAGE);
  try {
    const result = await sessionRequest(follow ? "follow" : "unfollow", { bioguideId });
    publish({ ...state, following: result.following });
    return result.following;
  } catch (error) {
    if (error.status === 401) publish({ ...SERVER_STATE, status: "signedOut" });
    throw error;
  }
}

export function useFollowing() {
  useEffect(() => { load(); }, []);
  return useSyncExternalStore(subscribe, () => state, () => SERVER_STATE);
}
