package pprof

import (
	"fmt"
	"strconv"
	"strings"
)

// SampleIndexByName returns the appropriate index for a value of sample index.
// If numeric, it returns the number, otherwise it looks up the text in the
// profile sample types.
func (p *Profile) SampleIndexByName(sampleIndex string) (int, error) {
	if sampleIndex == "" {
		if dst := p.DefaultSampleType; dst != "" {
			for i, t := range sampleTypes(p) {
				if t == dst {
					return i, nil
				}
			}
		}
		// By default select the last sample value
		return len(p.SampleType) - 1, nil
	}
	if i, err := strconv.Atoi(sampleIndex); err == nil {
		if i < 0 || i >= len(p.SampleType) {
			return 0, fmt.Errorf("sample_index %s is outside the range [0..%d]", sampleIndex, len(p.SampleType)-1)
		}
		return i, nil
	}

	// Remove the inuse_ prefix to support legacy pprof options
	// "inuse_space" and "inuse_objects" for profiles containing types
	// "space" and "objects".
	noInuse := strings.TrimPrefix(sampleIndex, "inuse_")
	for i, t := range p.SampleType {
		if t.Type == sampleIndex || t.Type == noInuse {
			return i, nil
		}
	}

	return 0, fmt.Errorf("sample_index %q must be one of: %v", sampleIndex, sampleTypes(p))
}

func sampleTypes(p *Profile) []string {
	types := make([]string, len(p.SampleType))
	for i, t := range p.SampleType {
		types[i] = t.Type
	}
	return types
}
