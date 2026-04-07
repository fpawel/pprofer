package simple_json

import (
	"encoding/json"
	"fmt"
	"net/http"

	requestError "github.com/fpawel/pprofer/internal/httph/middleware/request_error"
	"github.com/fpawel/pprofer/internal/httph/status"
)

type (
	ResponseFunc     func(r *http.Request) (any, error)
	MustResponseFunc func(r *http.Request) any
)

const (
	HeaderContentType = "Content-Type"
	ContentTypeJSON   = "application/json"
)

func MustResponse(responderFunc MustResponseFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, r, responderFunc(r))
	}
}

func Value(value any) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, r, value)
	}
}

func Response(responderFunc ResponseFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resp, err := responderFunc(r)

		if err != nil {
			requestError.AddError(r.Context(), err)
			status.WriteError(w, err)
			return
		}
		writeJSON(w, r, resp)
	}
}

func writeJSON(w http.ResponseWriter, r *http.Request, resp any) {
	w.Header().Set(HeaderContentType, ContentTypeJSON)
	if err := json.NewEncoder(w).Encode(resp); err != nil {
		requestError.AddError(r.Context(), fmt.Errorf("could not encode response: %w", err))
	}
}
