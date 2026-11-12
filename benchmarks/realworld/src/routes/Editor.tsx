// A Markdown editor with two previews: react-markdown with GitHub tables, and marked's HTML,
// sanitized by DOMPurify, its code blocks highlighted by highlight.js.
import { useMemo, useState } from 'react';
import { Box, Paper, TextField, Typography } from '@mui/material';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import json from 'highlight.js/lib/languages/json';
import styled from 'styled-components';

hljs.registerLanguage('javascript', javascript);
hljs.registerLanguage('typescript', typescript);
hljs.registerLanguage('json', json);

const marked = new Marked({
  async: false,
  gfm: true,
  renderer: {
    code({ text, lang }) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'javascript';
      return `<pre class="hljs"><code>${hljs.highlight(text, { language }).value}</code></pre>`;
    },
  },
});

const START = `# Release notes

Version **2.4.1** ships the _regional_ dashboard.

| Region | Owner | Status |
| ------ | ----- | ------ |
| North  | Ada   | done   |
| South  | Alan  | review |

- [x] Charts
- [ ] Exports

\`\`\`ts
export function total(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0);
}
\`\`\`

<img src=x onerror="alert('xss')">
`;

const Pane = styled(Paper)`
  padding: 12px;
  min-height: 240px;
  overflow: auto;
  & table {
    border-collapse: collapse;
  }
  & td,
  & th {
    border: 1px solid #ccc;
    padding: 2px 6px;
  }
`;

export default function Editor() {
  const [text, setText] = useState(START);
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text) as string), [text]);
  const words = text.split(/\s+/).filter(Boolean).length;
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2 }}>
      <TextField name="markdown" multiline minRows={14} value={text} onChange={(e) => setText(e.target.value)} />
      <Pane variant="outlined">
        <Typography variant="overline">Preview</Typography>
        <Markdown remarkPlugins={[remarkGfm]}>{text}</Markdown>
      </Pane>
      <Pane variant="outlined">
        <Typography variant="overline">Sanitized HTML · {words} words</Typography>
        <div dangerouslySetInnerHTML={{ __html: html }} />
      </Pane>
    </Box>
  );
}
