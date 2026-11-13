// Parse each file of a list with Oxc's or SWC's parser, natively, on one thread: the best and the
// median of N timed parses after three untimed ones, in microseconds; or, with ROUNDS = 1 and
// WARMUP = 0, one timed pass over a whole corpus. Each file's goal is settled first: a module,
// else a script. The tree is dropped after the timer stops.
//   parsebench oxc|swc LIST ROUNDS [WARMUP]
use std::time::Instant;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn is_ts(f: &str) -> bool { f.ends_with(".ts") || f.ends_with(".tsx") || f.ends_with(".mts") || f.ends_with(".cts") }
fn is_jsx(f: &str) -> bool { f.ends_with(".jsx") || f.ends_with(".tsx") }

// Parses once; true when it parsed without errors. The tree lives until `after` returns.
fn oxc(src: &str, f: &str, module: bool, timer: &mut dyn FnMut()) -> bool {
    use oxc_span::SourceType;
    let allocator = oxc_allocator::Allocator::default();
    let st = SourceType::default()
        .with_typescript(is_ts(f))
        .with_jsx(is_jsx(f))
        .with_module(module)
        .with_script(!module);
    let ret = oxc_parser::Parser::new(&allocator, src, st).parse();
    timer();
    !ret.fatal_error && ret.diagnostics.is_empty()
}

fn swc(src: &str, f: &str, module: bool, timer: &mut dyn FnMut()) -> bool {
    use swc_common::{sync::Lrc, FileName, SourceMap};
    use swc_ecma_parser::{lexer::Lexer, EsSyntax, Parser, StringInput, Syntax, TsSyntax};
    let cm: Lrc<SourceMap> = Default::default();
    let fm = cm.new_source_file(Lrc::new(FileName::Anon), src.to_string());
    let syntax = if is_ts(f) {
        Syntax::Typescript(TsSyntax { tsx: is_jsx(f), decorators: true, ..Default::default() })
    } else {
        Syntax::Es(EsSyntax { jsx: is_jsx(f), allow_return_outside_function: !module, ..Default::default() })
    };
    let lexer = Lexer::new(syntax, Default::default(), StringInput::from(&*fm), None);
    let mut parser = Parser::new_from(lexer);
    let ok = if module { parser.parse_module().map(|_| ()) } else { parser.parse_script().map(|_| ()) };
    timer();
    ok.is_ok() && parser.take_errors().is_empty()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let which = args[1].clone();
    let list = std::fs::read_to_string(&args[2]).unwrap();
    let rounds: usize = args[3].parse().unwrap();
    let warm: usize = args.get(4).map(|w| w.parse().unwrap()).unwrap_or(3);
    let parse: fn(&str, &str, bool, &mut dyn FnMut()) -> bool = match which.as_str() {
        "oxc" => oxc,
        "swc" => swc,
        _ => panic!("no parser {which}"),
    };
    let files: Vec<&str> = list.lines().filter(|l| !l.is_empty()).collect();
    let goal = |src: &str, f: &str| -> Option<bool> {
        [true, false].into_iter().find(|&m| parse(src, f, m, &mut || {}))
    };
    if rounds == 1 && warm == 0 {
        let srcs: Vec<String> = files.iter().map(|f| String::from_utf8_lossy(&std::fs::read(f).unwrap()).into_owned()).collect();
        let goals: Vec<Option<bool>> = srcs.iter().zip(&files).map(|(s, f)| goal(s, f)).collect();
        let (mut bytes, mut failed, mut ns) = (0usize, 0usize, 0u128);
        for i in 0..files.len() {
            let Some(m) = goals[i] else { failed += 1; continue };
            let t0 = Instant::now();
            parse(&srcs[i], files[i], m, &mut || ns += t0.elapsed().as_nanos());
            bytes += srcs[i].len();
        }
        println!("CORPUS {which} files {} failed {failed} bytes {bytes} us {}", files.len(), ns / 1000);
        return;
    }
    for f in files {
        let src = std::fs::read_to_string(f).unwrap();
        let Some(m) = goal(&src, f) else { println!("SKIP {f}"); continue };
        for _ in 0..warm { parse(&src, f, m, &mut || {}); }
        let mut times = Vec::new();
        for _ in 0..rounds {
            let t0 = Instant::now();
            let mut took = 0u128;
            parse(&src, f, m, &mut || took = t0.elapsed().as_micros());
            times.push(took);
        }
        times.sort();
        println!("BENCH {f} {} {} {}", src.len(), times[0], times[rounds / 2]);
    }
}
