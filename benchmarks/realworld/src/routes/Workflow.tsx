// An order's approval workflow, and the state libraries a codebase collects over the years: an
// XState machine, a MobX task list, a jotai counter, a zustand filter store updated with immer, RxJS
// over the events, and a socket.io client that stays offline.
import { useEffect, useMemo, useState } from 'react';
import { Box, Button, Checkbox, FormControlLabel, Stack, Typography } from '@mui/material';
import { createMachine, assign } from 'xstate';
import { useMachine } from '@xstate/react';
import { makeAutoObservable } from 'mobx';
import { observer } from 'mobx-react-lite';
import { atom, useAtom } from 'jotai';
import { create } from 'zustand';
import { produce } from 'immer';
import { Subject, scan, map, filter, startWith } from 'rxjs';
import { io } from 'socket.io-client';

const approval = createMachine({
  id: 'approval',
  initial: 'draft',
  context: { revisions: 0 },
  states: {
    draft: { on: { SUBMIT: 'review' } },
    review: {
      on: {
        APPROVE: 'approved',
        REJECT: { target: 'draft', actions: assign({ revisions: ({ context }) => context.revisions + 1 }) },
      },
    },
    approved: { on: { SHIP: 'shipped' } },
    shipped: { type: 'final' },
  },
});

class Tasks {
  items = [
    { id: 1, title: 'Check stock', done: true },
    { id: 2, title: 'Confirm address', done: false },
    { id: 3, title: 'Print label', done: false },
  ];
  constructor() {
    makeAutoObservable(this);
  }
  toggle(id: number) {
    const task = this.items.find((t) => t.id === id);
    if (task) task.done = !task.done;
  }
  get remaining() {
    return this.items.filter((t) => !t.done).length;
  }
}

const TaskList = observer(({ tasks }: { tasks: Tasks }) => (
  <Box>
    {tasks.items.map((t) => (
      <FormControlLabel key={t.id} control={<Checkbox checked={t.done} onChange={() => tasks.toggle(t.id)} />} label={t.title} />
    ))}
    <Typography>{tasks.remaining} tasks remaining</Typography>
  </Box>
));

const approvals = atom(0);

interface Filters {
  tags: string[];
  add(tag: string): void;
}
const useFilters = create<Filters>((set) => ({
  tags: ['priority'],
  add: (tag) => set(produce((state: Filters) => void state.tags.push(tag))),
}));

export default function Workflow() {
  const [snapshot, send] = useMachine(approval);
  const [count, setCount] = useAtom(approvals);
  const tasks = useMemo(() => new Tasks(), []);
  const { tags, add } = useFilters();
  const events = useMemo(() => new Subject<string>(), []);
  const [log, setLog] = useState({ seen: 0, last: 'none' });
  const socket = useMemo(() => io('http://127.0.0.1:9', { autoConnect: false, transports: ['websocket'] }), []);

  useEffect(() => {
    const sub = events
      .pipe(
        filter((e) => e !== 'NOOP'),
        map((e) => e.toLowerCase()),
        scan((acc, e) => ({ seen: acc.seen + 1, last: e }), { seen: 0, last: 'none' }),
        startWith({ seen: 0, last: 'none' }),
      )
      .subscribe(setLog);
    return () => sub.unsubscribe();
  }, [events]);

  const fire = (event: 'SUBMIT' | 'APPROVE' | 'REJECT' | 'SHIP') => {
    send({ type: event });
    events.next(event);
    if (event === 'APPROVE') setCount((c) => c + 1);
  };

  return (
    <Stack spacing={2}>
      <Typography variant="h5">State: {String(snapshot.value)}</Typography>
      <Typography>
        Revisions {snapshot.context.revisions} · approvals {count} · events {log.seen} (last {log.last}) · socket{' '}
        {socket.connected ? 'online' : 'offline'}
      </Typography>
      <Stack direction="row" spacing={1}>
        <Button name="submit" onClick={() => fire('SUBMIT')} disabled={!snapshot.can({ type: 'SUBMIT' })}>
          Submit for review
        </Button>
        <Button name="approve" onClick={() => fire('APPROVE')} disabled={!snapshot.can({ type: 'APPROVE' })}>
          Approve
        </Button>
        <Button name="reject" onClick={() => fire('REJECT')} disabled={!snapshot.can({ type: 'REJECT' })}>
          Reject
        </Button>
        <Button name="ship" onClick={() => fire('SHIP')} disabled={!snapshot.can({ type: 'SHIP' })}>
          Ship
        </Button>
      </Stack>
      <TaskList tasks={tasks} />
      <Box>
        Tags: {tags.join(', ')}{' '}
        <Button size="small" onClick={() => add(`tag-${tags.length}`)}>
          Add tag
        </Button>
      </Box>
    </Stack>
  );
}
