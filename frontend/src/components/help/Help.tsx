import {
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import type * as React from 'react';

import './help.css';

import { getHelp } from '../../help/registry';

import HelpIcon from './HelpIcon';
import HelpPopover from './HelpPopover';

type Props = {
  topic: string;
};

export default function Help({
  topic,
}: Props): React.JSX.Element | null {
  const [open, setOpen] = useState(false);

  const rootRef = useRef<HTMLSpanElement | null>(null);

  const generatedId = useId();

  const popoverId =
    `cx-help-${generatedId.replace(/:/g, '')}`;

  const help = getHelp(topic);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (
      event: MouseEvent | TouchEvent,
    ): void => {
      const root = rootRef.current;

      if (
        root
        && event.target instanceof Node
        && !root.contains(event.target)
      ) {
        setOpen(false);
      }
    };

    const onKeyDown = (
      event: KeyboardEvent,
    ): void => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener(
      'mousedown',
      onPointerDown,
    );

    document.addEventListener(
      'touchstart',
      onPointerDown,
    );

    document.addEventListener(
      'keydown',
      onKeyDown,
    );

    return () => {
      document.removeEventListener(
        'mousedown',
        onPointerDown,
      );

      document.removeEventListener(
        'touchstart',
        onPointerDown,
      );

      document.removeEventListener(
        'keydown',
        onKeyDown,
      );
    };
  }, [open]);

  if (!help) return null;

  return (
    <span
      ref={rootRef}
      className="cx-help"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={(event) => {
        if (
          !event.currentTarget.contains(
            event.relatedTarget,
          )
        ) {
          setOpen(false);
        }
      }}
    >
      <HelpIcon
        expanded={open}
        controls={popoverId}
        onClick={() => {
          setOpen((current) => !current);
        }}
      />

      {open && (
        <HelpPopover
          id={popoverId}
          help={help}
        />
      )}
    </span>
  );
}
