package httph

import (
	"net/http"

	logHTTP "github.com/fpawel/pprofer/internal/httph/middleware/log_http"
	"github.com/fpawel/pprofer/internal/httph/middleware/request_error"
	"github.com/fpawel/pprofer/internal/httph/middleware/requestid"
)

func Wrap(h http.Handler) http.Handler {
	return requestid.Handler(
		request_error.Middleware(
			logHTTP.Middleware(h),
		),
	)
}
