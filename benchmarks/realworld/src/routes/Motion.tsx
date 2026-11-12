// A release checklist that animates: framer-motion's layout animations, a Floating UI tooltip, and
// cards styled with styled-components and emotion through MUI.
import { useState } from 'react';
import { Button, Stack, Typography } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';
import { useFloating, useHover, useInteractions, offset, flip, shift, FloatingPortal } from '@floating-ui/react';
import styled from 'styled-components';
import clsx from 'clsx';

const Card = styled(motion.li)`
  list-style: none;
  padding: 8px 12px;
  margin: 4px 0;
  border-radius: 6px;
  background: #eef2f7;
  &.done {
    text-decoration: line-through;
    opacity: 0.6;
  }
`;

const STEPS = ['Freeze branch', 'Run migrations', 'Tag release', 'Announce'];

function Hint({ label, children }: { label: string; children: string }) {
  const [open, setOpen] = useState(false);
  const { refs, floatingStyles, context } = useFloating({ open, onOpenChange: setOpen, middleware: [offset(6), flip(), shift()] });
  const hover = useHover(context);
  const { getReferenceProps, getFloatingProps } = useInteractions([hover]);
  return (
    <>
      <span ref={refs.setReference} {...getReferenceProps()} style={{ borderBottom: '1px dotted' }}>
        {children}
      </span>
      {open && (
        <FloatingPortal>
          <div ref={refs.setFloating} style={{ ...floatingStyles, background: '#222', color: '#fff', padding: 4 }} {...getFloatingProps()}>
            {label}
          </div>
        </FloatingPortal>
      )}
    </>
  );
}

export default function Motion() {
  const [done, setDone] = useState<string[]>([]);
  const [hidden, setHidden] = useState(false);
  const remaining = STEPS.filter((s) => !done.includes(s));
  return (
    <Stack spacing={1}>
      <Typography variant="h5">
        Release checklist (<Hint label="Steps run in order">{`${remaining.length} left`}</Hint>)
      </Typography>
      <Button name="toggle" onClick={() => setHidden((h) => !h)}>
        {hidden ? 'Show finished' : 'Hide finished'}
      </Button>
      <motion.ul layout style={{ padding: 0 }}>
        <AnimatePresence initial={false}>
          {STEPS.filter((s) => !hidden || !done.includes(s)).map((s) => (
            <Card
              key={s}
              layout
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className={clsx({ done: done.includes(s) })}
              onClick={() => setDone((d) => (d.includes(s) ? d.filter((x) => x !== s) : [...d, s]))}
            >
              {s}
            </Card>
          ))}
        </AnimatePresence>
      </motion.ul>
      <Typography>Motion ready</Typography>
    </Stack>
  );
}
