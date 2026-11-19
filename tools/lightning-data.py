#!/usr/bin/env python3
"""Writes src/css/compat-data.rules from lightningcss's own generated browser data.

lightningcss (v1.33.0) generates src/compat.rs (which browser versions have each feature) and
src/prefixes.rs (which versions need a vendor prefix for each feature) from caniuse and mdn. This
reads those two files and writes the same facts as data for css.compat: for each feature, the
lowest version of each browser that has it (or that the browser never does), and for each prefix
feature, the version ranges in which each browser needs each prefix.

usage: python3 tools/lightning-data.py LIGHTNINGCSS-SOURCE-DIR
"""
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])


def kebab(name):
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', '-', name).lower()


def feature_arms(lines):
    """(features, body lines) for each `Feature::A | Feature::B => { … }` arm of a match."""
    arms = []
    names = []
    body = None
    for line in lines:
        stripped = line.strip()
        heads = re.findall(r'Feature::([A-Za-z0-9]+)', stripped)
        if heads and (stripped.startswith('Feature::') or stripped.startswith('| Feature::')):
            if body is not None:
                arms.append((names, body))
                names, body = [], None
            names.extend(heads)
            if stripped.endswith('=> {'):
                body = []
            continue
        if body is not None:
            body.append(stripped)
    if body is not None:
        arms.append((names, body))
    return arms


def compat():
    text = (src / 'src' / 'compat.rs').read_text()
    start = text.index('pub fn is_compatible')
    end = text.index('pub fn is_partially_compatible')
    lines = text[start:end].splitlines()
    out = {}
    for names, body in feature_arms(lines):
        reqs = []
        browser = None
        for line in body:
            m = re.match(r'if let Some\(version\) = browsers\.([a-z_]+) \{', line)
            if m:
                browser = m.group(1)
                continue
            m = re.match(r'if version < (\d+) \{', line)
            if m and browser:
                reqs.append((browser, int(m.group(1))))
                browser = None
                continue
            for b in re.findall(r'browsers\.([a-z_]+)\.is_some\(\)', line):
                reqs.append((b, -1))
        for name in names:
            out[kebab(name)] = reqs
    return out


def prefixes():
    text = (src / 'src' / 'prefixes.rs').read_text()
    start = text.index('pub fn prefixes_for')
    end = text.index('pub fn is_flex_2009')
    lines = text[start:end].splitlines()
    out = {}
    for names, body in feature_arms(lines):
        rules = []
        browser = None
        low, high = 0, -1
        for line in body:
            m = re.match(r'if let Some\(version\) = browsers\.([a-z_]+) \{', line)
            if m:
                browser = m.group(1)
                low, high = 0, -1
                continue
            m = re.match(r'if browsers\.([a-z_]+)\.is_some\(\) \{', line)
            if m:
                browser = m.group(1)
                low, high = 0, -1
                continue
            m = re.match(r'if version == (\d+) \{', line)
            if m:
                low = high = int(m.group(1))
                continue
            m = re.match(r'if version >= (\d+) && version <= (\d+) \{', line)
            if m:
                low, high = int(m.group(1)), int(m.group(2))
                continue
            m = re.match(r'if version <= (\d+) \{', line)
            if m:
                low, high = 0, int(m.group(1))
                continue
            m = re.match(r'if version >= (\d+) \{', line)
            if m:
                low, high = int(m.group(1)), -1
                continue
            m = re.match(r'prefixes \|= VendorPrefix::([A-Za-z]+);', line)
            if m:
                rules.append((browser, low, high, m.group(1)))
        for name in names:
            out[kebab(name)] = rules
    return out


def ranges(fn_name):
    text = (src / 'src' / 'prefixes.rs').read_text()
    body = text[text.index('pub fn ' + fn_name):]
    body = body[:body.index('\n}\n')]
    found = []
    browser = None
    for line in body.splitlines():
        line = line.strip()
        m = re.match(r'if let Some\(version\) = browsers\.([a-z_]+) \{', line)
        if m:
            browser = m.group(1)
        m = re.match(r'if version >= (\d+) && version <= (\d+) \{', line)
        if m:
            found.append((browser, int(m.group(1)), int(m.group(2))))
    return found


prefix_bits = {'WebKit': 2, 'Moz': 4, 'Ms': 8, 'O': 16}

lines = []
lines.append('# Which browser versions have each feature lightningcss asks about, and which need a vendor prefix')
lines.append('# for each feature that may have one: lightningcss 1.33.0\'s own data (src/compat.rs and')
lines.append('# src/prefixes.rs, which it generates from caniuse and mdn), written as data by')
lines.append('# tools/lightning-data.py. Do not edit by hand. Versions are lightningcss\'s: major << 16 | minor << 8.')
lines.append('rules css.compat-data')
lines.append('')
lines.append('# A browser has the feature from version `min` on; -1 when it has never had it.')
lines.append('record Since { browser: Text, min: Int }')
lines.append('')
lines.append('# A browser needs `prefix` (lightningcss\'s bits: 2 webkit, 4 moz, 8 ms, 16 o) from `low` to `high`')
lines.append('# (-1: and every version after).')
lines.append('record Needs { browser: Text, low: Int, high: Int, prefix: Int }')
lines.append('')
lines.append('record Span { browser: Text, low: Int, high: Int }')
lines.append('')
lines.append('const features: {Text:[Since]} = {')
c = compat()
entries = []
for name in sorted(c):
    reqs = ', '.join(f'Since(browser: "{b}", min: {v})' for b, v in c[name])
    entries.append(f'  "{name}": [{reqs}]')
lines.append(',\n'.join(entries))
lines.append('}')
lines.append('')
lines.append('const prefixes: {Text:[Needs]} = {')
p = prefixes()
entries = []
for name in sorted(p):
    rules = ', '.join(f'Needs(browser: "{b}", low: {lo}, high: {hi}, prefix: {prefix_bits[x]})' for b, lo, hi, x in p[name])
    entries.append(f'  "{name}": [{rules}]')
lines.append(',\n'.join(entries))
lines.append('}')
lines.append('')
for fn_name in ['is_flex_2009', 'is_webkit_gradient']:
    spans = ', '.join(f'Span(browser: "{b}", low: {lo}, high: {hi})' for b, lo, hi in ranges(fn_name))
    lines.append(f'const {fn_name.replace("_", "-")}: [Span] = [{spans}]')
    lines.append('')

Path('src/css/compat-data.rules').write_text('\n'.join(lines))
print('features', len(c), 'prefix features', len(p))
