package pprof

import (
	"io"
	"reflect"
)

type Metrics struct {
	Items  []ReportEntry `json:"items"`
	Labels []string      `json:"labels"`
	Total  int64         `json:"total"`
}

// GetMetrics returns the metrics data of either inuse_space or cpu
//
// reader contains bytes in the format of .pb or pg.gz
func GetMetrics(reader io.Reader) (*Metrics, error) {

	prof, err := Parse(reader)

	if err != nil {
		return nil, err
	}

	return getMetrics(prof, err)

}

// GetMetricsFromData returns the metrics data of either inuse_space or cpu
//
// reader contains bytes in the format of .pb or pg.gz
func GetMetricsFromData(data []byte) (*Metrics, error) {

	prof, err := ParseData(data)

	if err != nil {
		return nil, err
	}

	return getMetrics(prof, err)

}

func getMetrics(prof *Profile, err error) (*Metrics, error) {
	for _, loc := range prof.Location {
		loc.Address = 0
	}

	index, err := prof.SampleIndexByName(prof.DefaultSampleType)
	if err != nil {
		return nil, err
	}

	o := Options{
		OutputFormat: Text,
		NodeFraction: 0,
		SampleType:   prof.DefaultSampleType,
		SampleValue: func(s []int64) int64 {
			return s[index]
		},
	}

	rpt := New(prof, &o)

	items, labels := rpt.GetEntries()

	v := reflect.ValueOf(*rpt)
	total := v.FieldByName("total").Int()

	return &Metrics{
		Items:  items,
		Labels: labels,
		Total:  total,
	}, nil
}
