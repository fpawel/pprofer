package status

import (
	"errors"
	"fmt"
	"net/http"
)

type Error struct {
	Code int
	Err  string
}

func (err Error) Error() string {
	return err.Err
}

func NewError(code int, err error) error {
	return Error{Code: code, Err: err.Error()}
}

func NewErrorCodeMsg(code int, msg string) error {
	return Error{Code: code, Err: msg}
}

func NewErrorCodeMsgFormat(code int, format string, args ...any) error {
	return Error{Code: code, Err: fmt.Sprintf(format, args...)}
}

func WriteError(w http.ResponseWriter, err error) {
	http.Error(w, err.Error(), GetFromError(err))
}

func GetFromError(err error) int {
	if err == nil {
		return http.StatusOK
	}
	code := http.StatusInternalServerError
	if e, ok := errors.AsType[Error](err); ok {
		code = e.Code
	}
	return code
}
