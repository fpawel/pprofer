package pprof

import (
	"context"
	"strconv"

	"github.com/fpawel/errorx"
	"github.com/imroc/req/v3"
)

type Client struct {
	*req.Client
}

func NewClient(pprofURL string) Client {
	return Client{
		Client: req.C().SetBaseURL(pprofURL),
	}
}

func (c Client) GetDebugPprof(ctx context.Context, profileType string, seconds int) ([]byte, error) {
	eb := errorx.WithShortFunction()

	request := c.Client.R().SetContext(ctx).SetPathParam("profileType", profileType)
	//request = request.SetQueryParam("debug", "2")

	if profileType == ProfTypeProfile || profileType == ProfTypeTrace {
		request = request.SetQueryParam("seconds", strconv.Itoa(seconds))
	}

	resp, err := request.Get("/debug/pprof/{profileType}")
	if err != nil {
		return nil, eb.WithFileLine().Wrap(err)
	}

	if resp.IsErrorState() {
		return nil, eb.WithFileLine().New(resp.GetStatus())
	}

	return resp.Bytes(), nil
}

func (c Client) GetMetrics(ctx context.Context, profileType string, seconds int) (*Metrics, error) {
	eb := errorx.WithShortFunction().WithArgs("profileType", profileType)
	data, err := c.GetDebugPprof(ctx, profileType, seconds)
	if err != nil {
		return nil, eb.WithFileLine().Wrap(err)
	}

	metrics, err := GetMetricsFromData(data)
	if err != nil {
		return nil, eb.WithFileLine().Wrap(err)
	}
	return metrics, nil
}
