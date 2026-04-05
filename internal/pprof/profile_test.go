package pprof

import (
	"os"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestParseData(t *testing.T) {
	data, err := os.ReadFile("../../heap.data")
	require.NoError(t, err)
	_, err = ParseData(data)
	require.NoError(t, err)
}
