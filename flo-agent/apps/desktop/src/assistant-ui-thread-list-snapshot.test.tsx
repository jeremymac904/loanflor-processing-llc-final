import { LazyMemoizeSubject } from "@assistant-ui/core/internal";
import { render } from "@testing-library/react";
import { useSyncExternalStore } from "react";

type ThreadListSnapshot = {
  mainThreadId: string;
  newThreadId: string | undefined;
  threadIds: readonly string[];
  archivedThreadIds: readonly string[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  threadItems: Record<string, never>;
};

function makeThreadListSubject() {
  let notify = () => {};
  let source: ThreadListSnapshot = {
    mainThreadId: "main",
    newThreadId: undefined,
    threadIds: [],
    archivedThreadIds: [],
    isLoading: false,
    isLoadingMore: false,
    hasMore: false,
    threadItems: {},
  };
  const subject = new LazyMemoizeSubject({
    path: {},
    getState: () => ({ ...source }),
    subscribe(callback: () => void) {
      notify = callback;
      return () => {
        if (notify === callback) notify = () => {};
      };
    },
  });
  return { subject, setSource: (next: ThreadListSnapshot) => (source = next), notify: () => notify() };
}

it("keeps the production thread-list snapshot stable before subscription", () => {
  const { subject, setSource, notify } = makeThreadListSubject();

  const first = subject.getState();
  const second = subject.getState();
  expect(second).toBe(first);

  subject.subscribe(() => {});
  setSource({ ...first, threadIds: ["thread-1"] });
  notify();
  expect(subject.getState()).not.toBe(first);
  expect(subject.getState().threadIds).toEqual(["thread-1"]);
});

it("does not loop when React subscribes to the production thread-list subject", () => {
  const { subject } = makeThreadListSubject();
  let renders = 0;

  function Probe() {
    const state = useSyncExternalStore(subject.subscribe.bind(subject), subject.getState, subject.getState);
    renders += 1;
    return <output data-testid="thread-count">{state.threadIds.length}</output>;
  }

  const { getByTestId } = render(<Probe />);
  expect(getByTestId("thread-count").textContent).toBe("0");
  expect(renders).toBeLessThan(5);
});

it("memoizes the direct subject contract used by the production runtime", () => {
  let value = { count: 0 };
  let notify = () => {};
  const subject = new LazyMemoizeSubject({
    path: {},
    getState: () => ({ ...value }),
    subscribe: (callback: () => void) => {
      notify = callback;
      return () => {};
    },
  });

  const first = subject.getState();
  expect(subject.getState()).toBe(first);
  subject.subscribe(() => {});
  value = { count: 1 };
  notify();
  expect(subject.getState()).not.toBe(first);
  expect(subject.getState().count).toBe(1);
});
