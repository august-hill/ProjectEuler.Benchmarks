package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

// Lang defines how to discover, build, and run solutions for one language.
// Most languages only need the declarative fields. Custom funcs override for special cases.
type Lang struct {
	Key         string // "c", "cpp", etc.
	Display     string // "C", "C++", etc.
	Repo        string // "ProjectEuler.C", etc.
	SrcFile     string // "main.c" — relative to problem dir
	SrcSubdir   bool   // true if source is in problem_NNN/<SrcFile>, false if flat (Python)
	BuildArgs   func(repoDir, probDir string) [][]string // nil = no build. Returns list of arg sets to try in order.
	RunArgs     func(repoDir, probDir string) (string, []string) // returns (binary, args)
	CleanFiles  []string // files to remove after run (relative to probDir)
	CompilerCmd []string // command to get compiler version, e.g. ["clang", "--version"]
	// Special hooks
	ExtraSourceFiles func(probDir string) []string                              // additional source files for SLOC (ARM64)
	BatchBuild       func(repoDir string, problems []string) (failed []string)  // C# two-phase
	PreBuild         func(repoDir, probDir, problem string) error               // Java: copy Bench.java
	SequentialBuild  bool                                                       // true = run build steps sequentially (ARM64: assemble then link)
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func tryBuild(argSets [][]string, dir string) error {
	var lastErr error
	for _, args := range argSets {
		cmd := exec.Command(args[0], args[1:]...)
		cmd.Dir = dir
		cmd.Stderr = nil
		cmd.Stdout = nil
		if err := cmd.Run(); err == nil {
			return nil
		} else {
			lastErr = err
		}
	}
	return fmt.Errorf("all build attempts failed: %v", lastErr)
}

var languages = []Lang{
	{
		Key: "c", Display: "C", Repo: "ProjectEuler.C",
		SrcFile: "main.c", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			cc := envOr("CC", "clang")
			flags := strings.Fields(envOr("CFLAGS", "-O2 -Wall"))
			args := append([]string{cc}, flags...)
			args = append(args, "-o", "main_bench", "main.c", "-lm")
			return [][]string{args}
		},
		RunArgs:     func(_, _ string) (string, []string) { return "./main_bench", nil },
		CleanFiles:  []string{"main_bench"},
		CompilerCmd: []string{"clang", "--version"},
	},
	{
		Key: "cpp", Display: "C++", Repo: "ProjectEuler.CPlusPlus",
		SrcFile: "main.cpp", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			cxx := envOr("CXX", "g++")
			flags := strings.Fields(envOr("CXXFLAGS", "-O2 -std=c++17 -I"+repoDir+"/include -I/opt/homebrew/include"))
			ldflags := "-lm -L/opt/homebrew/lib"
			base := append([]string{cxx}, flags...)
			base = append(base, "-o", "main_bench", "main.cpp")
			set1 := append(append([]string{}, base...), strings.Fields(ldflags)...)
			set2 := append(append([]string{}, set1...), "-lprimesieve")
			set3 := append(append([]string{}, set1...), "-lfmt")
			return [][]string{set1, set2, set3}
		},
		RunArgs:     func(_, _ string) (string, []string) { return "./main_bench", nil },
		CleanFiles:  []string{"main_bench"},
		CompilerCmd: []string{"g++", "--version"},
	},
	{
		Key: "rust", Display: "Rust", Repo: "ProjectEuler.Rust",
		SrcFile: "src/main.rs", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			return [][]string{{"cargo", "build", "--release", "-q"}}
		},
		RunArgs: func(_, probDir string) (string, []string) {
			name := filepath.Base(probDir)
			bin := filepath.Join("target", "release", name)
			if _, err := os.Stat(filepath.Join(probDir, bin)); err == nil {
				return bin, nil
			}
			// Fallback: find first executable in target/release
			entries, _ := os.ReadDir(filepath.Join(probDir, "target", "release"))
			for _, e := range entries {
				if e.IsDir() || strings.HasSuffix(e.Name(), ".d") {
					continue
				}
				info, _ := e.Info()
				if info != nil && info.Mode()&0111 != 0 {
					return filepath.Join("target", "release", e.Name()), nil
				}
			}
			return bin, nil // fallback to expected name
		},
		CompilerCmd: []string{"rustc", "--version"},
	},
	{
		Key: "go", Display: "Go", Repo: "ProjectEuler.Go",
		SrcFile: "main.go", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			return [][]string{{"go", "build", "-o", "main_bench", "."}}
		},
		RunArgs:     func(_, _ string) (string, []string) { return "./main_bench", nil },
		CleanFiles:  []string{"main_bench"},
		CompilerCmd: []string{"go", "version"},
	},
	{
		Key: "java", Display: "Java", Repo: "ProjectEuler.Java",
		SrcFile: "Main.java", SrcSubdir: true,
		PreBuild: func(repoDir, probDir, _ string) error {
			// Always copy latest Bench.java (ensures harness updates propagate)
			src := filepath.Join(repoDir, "Bench.java")
			data, err := os.ReadFile(src)
			if err != nil {
				return err
			}
			return os.WriteFile(filepath.Join(probDir, "Bench.java"), data, 0644)
		},
		BuildArgs: func(repoDir, probDir string) [][]string {
			return [][]string{{"javac", "Main.java", "Bench.java"}}
		},
		RunArgs:     func(_, _ string) (string, []string) { return "java", []string{"Main"} },
		CompilerCmd: []string{"java", "-version"},
	},
	{
		Key: "csharp", Display: "C#", Repo: "ProjectEuler.CSharp",
		SrcFile: "Program.cs", SrcSubdir: true,
		BatchBuild: func(repoDir string, problems []string) (failed []string) {
			for _, prob := range problems {
				probDir := filepath.Join(repoDir, "problem_"+prob)
				cmd := exec.Command("dotnet", "build", "-c", "Release", probDir)
				cmd.Stdout = nil
				cmd.Stderr = nil
				if err := cmd.Run(); err != nil {
					failed = append(failed, prob)
				}
			}
			return
		},
		RunArgs: func(_, probDir string) (string, []string) {
			name := filepath.Base(probDir)
			return filepath.Join("bin", "Release", "net10.0", name), nil
		},
		CompilerCmd: []string{"dotnet", "--version"},
	},
	{
		Key: "javascript", Display: "JavaScript", Repo: "ProjectEuler.JavaScript",
		SrcFile: "main.js", SrcSubdir: true,
		RunArgs:     func(_, _ string) (string, []string) { return "node", []string{"main.js"} },
		CompilerCmd: []string{"node", "--version"},
	},
	{
		Key: "arm64", Display: "ARM64", Repo: "ProjectEuler.ARM64",
		SrcFile: "main.c", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			cc := envOr("CC", "clang")
			solveS := filepath.Join(probDir, "solve.s")
			if _, err := os.Stat(solveS); err == nil {
				// Assembly + C: assemble then link
				return [][]string{
					{"as", "-o", "solve.o", "solve.s"},
					{cc, "-O2", "-o", "main_bench", "main.c", "solve.o", "-lm"},
				}
			}
			return [][]string{{cc, "-O2", "-o", "main_bench", "main.c", "-lm"}}
		},
		RunArgs:         func(_, _ string) (string, []string) { return "./main_bench", nil },
		CleanFiles:      []string{"main_bench", "solve.o"},
		SequentialBuild: true, // assemble first, then link — steps must run in order
		ExtraSourceFiles: func(probDir string) []string {
			s := filepath.Join(probDir, "solve.s")
			if _, err := os.Stat(s); err == nil {
				return []string{s}
			}
			return nil
		},
		CompilerCmd: []string{"clang", "--version"},
	},
	{
		Key: "python", Display: "Python", Repo: "ProjectEuler.Python",
		SrcFile: "", SrcSubdir: false, // flat structure, handled specially
		RunArgs: func(repoDir, probDir string) (string, []string) {
			// Note: probDir (repoDir/problem_NNN) doesn't exist as a directory for Python
			// (flat structure). We only use Base to extract the problem name for the filename.
			return "python3", []string{filepath.Base(probDir) + ".py"}
		},
		CompilerCmd: []string{"python3", "--version"},
	},
	{
		Key: "zig", Display: "Zig", Repo: "ProjectEuler.Zig",
		SrcFile: "main.zig", SrcSubdir: true,
		BuildArgs: func(repoDir, probDir string) [][]string {
			// Zig module resolution requires absolute paths so the bench module
			// (bench/bench.zig at repo root) can be found regardless of working directory.
			mainZig := filepath.Join(probDir, "main.zig")
			benchZig := filepath.Join(repoDir, "bench", "bench.zig")
			binOut := filepath.Join(probDir, "main_bench")
			return [][]string{{
				"zig", "build-exe", "-O", "ReleaseFast",
				"--dep", "bench",
				"-Mroot=" + mainZig,
				"-Mbench=" + benchZig,
				"-femit-bin=" + binOut,
			}}
		},
		RunArgs:     func(_, _ string) (string, []string) { return "./main_bench", nil },
		CleanFiles:  []string{"main_bench"},
		CompilerCmd: []string{"zig", "version"},
	},
}

func langByKey(key string) *Lang {
	for i := range languages {
		if languages[i].Key == key {
			return &languages[i]
		}
	}
	return nil
}

func allLangKeys() []string {
	keys := make([]string, len(languages))
	for i, l := range languages {
		keys[i] = l.Key
	}
	return keys
}
