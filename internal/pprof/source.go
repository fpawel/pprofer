package pprof

// This file contains routines related to the generation of annotated
// source listings.

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// printSource prints an annotated source listing, include all
// functions with samples that match the regexp rpt.options.symbol.
// The sources are sorted by function name and then by filename to
// eliminate potential nondeterminism.
func printSource(w io.Writer, rpt *Report) error {
	o := rpt.options
	g := rpt.newGraph(nil)

	// Identify all the functions that match the regexp provided.
	// Group nodes for each matching function.
	var functions Nodes
	functionNodes := make(map[string]Nodes)
	for _, n := range g.Nodes {
		if !o.Symbol.MatchString(n.Info.Name) {
			continue
		}
		if functionNodes[n.Info.Name] == nil {
			functions = append(functions, n)
		}
		functionNodes[n.Info.Name] = append(functionNodes[n.Info.Name], n)
	}
	functions.Sort(NameOrder)

	if len(functionNodes) == 0 {
		return fmt.Errorf("no matches found for regexp: %s", o.Symbol)
	}

	sourcePath := o.SourcePath
	if sourcePath == "" {
		wd, err := os.Getwd()
		if err != nil {
			return fmt.Errorf("could not stat current dir: %v", err)
		}
		sourcePath = wd
	}
	reader := newSourceReader(sourcePath, o.TrimPath)

	fmt.Fprintf(w, "Total: %s\n", rpt.formatValue(rpt.total))
	for _, fn := range functions {
		name := fn.Info.Name

		// Identify all the source files associated to this function.
		// Group nodes for each source file.
		var sourceFiles Nodes
		fileNodes := make(map[string]Nodes)
		for _, n := range functionNodes[name] {
			if n.Info.File == "" {
				continue
			}
			if fileNodes[n.Info.File] == nil {
				sourceFiles = append(sourceFiles, n)
			}
			fileNodes[n.Info.File] = append(fileNodes[n.Info.File], n)
		}

		if len(sourceFiles) == 0 {
			fmt.Fprintf(w, "No source information for %s\n", name)
			continue
		}

		sourceFiles.Sort(FileOrder)

		// Print each file associated with this function.
		for _, fl := range sourceFiles {
			filename := fl.Info.File
			fns := fileNodes[filename]
			flatSum, cumSum := fns.Sum()

			fnodes, _, err := getSourceFromFile(filename, reader, fns, 0, 0)
			fmt.Fprintf(w, "ROUTINE ======================== %s in %s\n", name, filename)
			fmt.Fprintf(w, "%10s %10s (flat, cum) %s of Total\n",
				rpt.formatValue(flatSum), rpt.formatValue(cumSum),
				Percentage(cumSum, rpt.total))

			if err != nil {
				fmt.Fprintf(w, " Error: %v\n", err)
				continue
			}

			for _, fn := range fnodes {
				fmt.Fprintf(w, "%10s %10s %6d:%s\n", valueOrDot(fn.Flat, rpt), valueOrDot(fn.Cum, rpt), fn.Info.Lineno, fn.Info.Name)
			}
		}
	}
	return nil
}

// WebListData holds the data needed to generate HTML source code listing.
type WebListData struct {
	Total string
	Files []WebListFile
}

// WebListFile holds the per-file information for HTML source code listing.
type WebListFile struct {
	Funcs []WebListFunc
}

// WebListFunc holds the per-function information for HTML source code listing.
type WebListFunc struct {
	Name       string
	File       string
	Flat       string
	Cumulative string
	Percent    string
	Lines      []WebListLine
}

// WebListLine holds the per-source-line information for HTML source code listing.
type WebListLine struct {
	SrcLine      string
	HTMLClass    string
	Line         int
	Flat         string
	Cumulative   string
	Instructions []WebListInstruction
}

// WebListInstruction holds the per-instruction information for HTML source code listing.
type WebListInstruction struct {
	NewBlock     bool // Insert marker that indicates separation from previous block
	Flat         string
	Cumulative   string
	Synthetic    bool
	Address      uint64
	Disasm       string
	FileLine     string
	InlinedCalls []WebListCall
}

// WebListCall holds the per-inlined-call information for HTML source code listing.
type WebListCall struct {
	SrcLine  string
	FileBase string
	Line     int
}

// synthAsm is the special disassembler value used for instructions without an object file.
const synthAsm = ""

// getSourceFromFile collects the sources of a function from a source
// file and annotates it with the samples in fns. Returns the sources
// as nodes, using the info.name field to hold the source code.
func getSourceFromFile(file string, reader *sourceReader, fns Nodes, start, end int) (Nodes, string, error) {
	lineNodes := make(map[int]Nodes)

	// Collect source coordinates from profile.
	const margin = 5 // Lines before first/after last sample.
	if start == 0 {
		if fns[0].Info.StartLine != 0 {
			start = fns[0].Info.StartLine
		} else {
			start = fns[0].Info.Lineno - margin
		}
	} else {
		start -= margin
	}
	if end == 0 {
		end = fns[0].Info.Lineno
	}
	end += margin
	for _, n := range fns {
		lineno := n.Info.Lineno
		nodeStart := n.Info.StartLine
		if nodeStart == 0 {
			nodeStart = lineno - margin
		}
		nodeEnd := lineno + margin
		if nodeStart < start {
			start = nodeStart
		} else if nodeEnd > end {
			end = nodeEnd
		}
		lineNodes[lineno] = append(lineNodes[lineno], n)
	}
	if start < 1 {
		start = 1
	}

	var src Nodes
	for lineno := start; lineno <= end; lineno++ {
		line, ok := reader.line(file, lineno)
		if !ok {
			break
		}
		flat, cum := lineNodes[lineno].Sum()
		src = append(src, &Node{
			Info: NodeInfo{
				Name:   strings.TrimRight(line, "\n"),
				Lineno: lineno,
			},
			Flat: flat,
			Cum:  cum,
		})
	}
	if err := reader.fileError(file); err != nil {
		return nil, file, err
	}
	return src, file, nil
}

// sourceReader provides access to source code with caching of file contents.
type sourceReader struct {
	// searchPath is a filepath.ListSeparator-separated list of directories where
	// source files should be searched.
	searchPath string

	// trimPath is a filepath.ListSeparator-separated list of paths to trim.
	trimPath string

	// files maps from path name to a list of lines.
	// files[*][0] is unused since line numbering starts at 1.
	files map[string][]string

	// errors collects errors encountered per file. These errors are
	// consulted before returning out of these module.
	errors map[string]error
}

func newSourceReader(searchPath, trimPath string) *sourceReader {
	return &sourceReader{
		searchPath,
		trimPath,
		make(map[string][]string),
		make(map[string]error),
	}
}

func (reader *sourceReader) fileError(path string) error {
	return reader.errors[path]
}

// line returns the line numbered "lineno" in path, or _,false if lineno is out of range.
func (reader *sourceReader) line(path string, lineno int) (string, bool) {
	lines, ok := reader.files[path]
	if !ok {
		// Read and cache file contents.
		lines = []string{""} // Skip 0th line
		f, err := openSourceFile(path, reader.searchPath, reader.trimPath)
		if err != nil {
			reader.errors[path] = err
		} else {
			s := bufio.NewScanner(f)
			for s.Scan() {
				lines = append(lines, s.Text())
			}
			f.Close()
			if s.Err() != nil {
				reader.errors[path] = err
			}
		}
		reader.files[path] = lines
	}
	if lineno <= 0 || lineno >= len(lines) {
		return "", false
	}
	return lines[lineno], true
}

// openSourceFile opens a source file from a name encoded in a profile. File
// names in a profile after can be relative paths, so search them in each of
// the paths in searchPath and their parents. In case the profile contains
// absolute paths, additional paths may be configured to trim from the source
// paths in the profile. This effectively turns the path into a relative path
// searching it using searchPath as usual).
func openSourceFile(path, searchPath, trim string) (*os.File, error) {
	path = trimPath(path, trim, searchPath)
	// If file is still absolute, require file to exist.
	if filepath.IsAbs(path) {
		f, err := os.Open(path)
		return f, err
	}
	// Scan each component of the path.
	for _, dir := range filepath.SplitList(searchPath) {
		// Search up for every parent of each possible path.
		for {
			filename := filepath.Join(dir, path)
			if f, err := os.Open(filename); err == nil {
				return f, nil
			}
			parent := filepath.Dir(dir)
			if parent == dir {
				break
			}
			dir = parent
		}
	}

	return nil, fmt.Errorf("could not find file %s on path %s", path, searchPath)
}

// trimPath cleans up a path by removing prefixes that are commonly
// found on profiles plus configured prefixes.
// TODO(aalexand): Consider optimizing out the redundant work done in this
// function if it proves to matter.
func trimPath(pth, trimPth, searchPth string) string {
	// Keep path variable intact as it's used below to form the return value.
	sPath, searchPth := filepath.ToSlash(pth), filepath.ToSlash(searchPth)
	if trimPth == "" {
		// If the trim path is not configured, try to guess it heuristically:
		// search for basename of each search path in the original path and, if
		// found, strip everything up to and including the basename. So, for
		// example, given original path "/some/remote/path/my-project/foo/bar.c"
		// and search path "/my/local/path/my-project" the heuristic will return
		// "/my/local/path/my-project/foo/bar.c".
		for _, dir := range filepath.SplitList(searchPth) {
			want := "/" + filepath.Base(dir) + "/"
			if found := strings.Index(sPath, want); found != -1 {
				return pth[found+len(want):]
			}
		}
	}
	// Trim configured trim prefixes.
	trimPaths := append(filepath.SplitList(filepath.ToSlash(trimPth)), "/proc/self/cwd/./", "/proc/self/cwd/")
	for _, trimPath := range trimPaths {
		if !strings.HasSuffix(trimPath, "/") {
			trimPath += "/"
		}
		if strings.HasPrefix(sPath, trimPath) {
			return pth[len(trimPath):]
		}
	}
	return pth
}
