// esbuild's own parser (js_parser.Parse: parse and visit, as a build does), natively (GOMAXPROCS=1
// for one thread, its garbage collector too):
// the best and median of N timed parses after three untimed ones, in microseconds; or with
// ROUNDS = 1 and WARMUP = 0, one timed pass over a whole corpus.
//   parsebench LIST ROUNDS [WARMUP]
package main

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/evanw/esbuild/internal/config"
	"github.com/evanw/esbuild/internal/js_parser"
	"github.com/evanw/esbuild/internal/logger"
)

func parse(src, f string) bool {
	ts := strings.HasSuffix(f, ".ts") || strings.HasSuffix(f, ".tsx") || strings.HasSuffix(f, ".mts") || strings.HasSuffix(f, ".cts")
	jsx := strings.HasSuffix(f, ".jsx") || strings.HasSuffix(f, ".tsx")
	log := logger.NewDeferLog(logger.DeferLogAll, nil)
	source := logger.Source{KeyPath: logger.Path{Text: f}, PrettyPaths: logger.PrettyPaths{Rel: f, Abs: f}, Contents: src}
	_, ok := js_parser.Parse(log, source, js_parser.OptionsFromConfig(&config.Options{
		// TypeScript projects such as VS Code use parameter decorators, as their tsconfig says.
		TS:  config.TSOptions{Parse: ts, Config: config.TSConfig{ExperimentalDecorators: config.True}},
		JSX: config.JSXOptions{Parse: jsx},
	}))
	return ok && !log.HasErrors()
}

func main() {
	list, _ := os.ReadFile(os.Args[1])
	rounds, _ := strconv.Atoi(os.Args[2])
	warm := 3
	if len(os.Args) > 3 {
		warm, _ = strconv.Atoi(os.Args[3])
	}
	var files []string
	for _, l := range strings.Split(string(list), "\n") {
		if l != "" {
			files = append(files, l)
		}
	}
	if rounds == 1 && warm == 0 {
		srcs := make([]string, len(files))
		good := make([]bool, len(files))
		for i, f := range files {
			b, _ := os.ReadFile(f)
			srcs[i] = string(b)
			good[i] = parse(srcs[i], f)
		}
		failed, bytes := 0, 0
		var total time.Duration
		for i, f := range files {
			if !good[i] {
				failed++
				continue
			}
			t0 := time.Now()
			parse(srcs[i], f)
			total += time.Since(t0)
			bytes += len(srcs[i])
		}
		fmt.Printf("CORPUS esbuild files %d failed %d bytes %d us %d\n", len(files), failed, bytes, total.Microseconds())
		return
	}
	for _, f := range files {
		b, _ := os.ReadFile(f)
		src := string(b)
		if !parse(src, f) {
			fmt.Printf("SKIP %s\n", f)
			continue
		}
		for i := 0; i < warm; i++ {
			parse(src, f)
		}
		times := make([]int64, rounds)
		for i := range times {
			t0 := time.Now()
			parse(src, f)
			times[i] = time.Since(t0).Microseconds()
		}
		sort.Slice(times, func(a, b int) bool { return times[a] < times[b] })
		fmt.Printf("BENCH %s %d %d %d\n", f, len(src), times[0], times[rounds/2])
	}
}
