package internal

import (
	"fmt"
	"log/slog"
	"os"
	"strings"

	"github.com/fpawel/pprofer/internal/logh"
)

var logger = slog.New(logh.NewLogHandler(slog.LevelDebug))

// ExitErr завершает выполнение программы при возникновении ошибки.
// Если err не равен nil, функция логирует ошибку с помощью slog.Error.
// Если передан один дополнительный аргумент, он используется для форматирования сообщения об ошибке.
// Если аргументов больше, они передаются в slog.Error как дополнительные детали.
// После логирования программа завершает выполнение с кодом 1.
func ExitErr(err error, args ...any) {
	if err == nil {
		return
	}
	LogErr(err)
	os.Exit(1)
}

func PanicErr(err error, args ...any) {
	if err == nil {
		return
	}
	panic(errArgs(err, args...))
}

func LogErr(err error, args ...any) {
	if err == nil {
		return
	}
	logger.Error(errArgs(err, args...).Error())
}

func errArgs(err error, args ...any) error {
	if err == nil {
		return nil
	}
	if len(args) == 1 {
		err = fmt.Errorf("%v: %w", args[0], err)
	} else {
		var sb strings.Builder
		for i := 0; i < len(args); i += 2 {
			if i != 0 {
				sb.WriteString(" ")
			}
			_, _ = fmt.Fprintf(&sb, "%s=%s", args[i], args[i+1])
		}
		if sb.Len() != 0 {
			err = fmt.Errorf("%w: %s", err, sb)
		}
	}
	return err
}
