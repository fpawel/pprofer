package main

import (
	"fmt"
	"math"
	"math/rand"
	"net/http"
	_ "net/http/pprof"
	"runtime"
	"sync"
	"time"
)

var (
	sink [][]byte
	mu   sync.Mutex
)

func cpuWorker(id int) {
	r := rand.New(rand.NewSource(time.Now().UnixNano() + int64(id)))

	for {
		var acc float64

		// Достаточно тяжёлая CPU-работа
		for i := 0; i < 5_000_000; i++ {
			x := float64((i % 1000) + 1)
			acc += math.Sqrt(x) * math.Sin(x) * math.Cos(x/3)
		}

		// Не даём компилятору выкинуть вычисления
		if acc == float64(r.Intn(1_000_000_000)) {
			fmt.Println("unreachable", acc)
		}

		// Короткая пауза, чтобы профиль был живой, но CPU не был 100% забит намертво
		time.Sleep(20 * time.Millisecond)
	}
}

func memoryWorker() {
	for {
		b := make([]byte, 256*1024) // 256 KB
		for i := 0; i < len(b); i += 4096 {
			b[i] = byte(rand.Intn(256))
		}

		mu.Lock()
		sink = append(sink, b)
		if len(sink) > 20 {
			sink = sink[1:]
		}
		mu.Unlock()

		time.Sleep(500 * time.Millisecond)
	}
}

func goroutineWorker() {
	for {
		go func() {
			buf := make([]byte, 1024)
			_ = buf
			time.Sleep(5 * time.Second)
		}()
		time.Sleep(500 * time.Millisecond)
	}
}

func main() {
	runtime.SetBlockProfileRate(1)
	runtime.SetMutexProfileFraction(1)

	const addr = "localhost:6060"

	fmt.Println("http://" + addr)

	go func() {
		if err := http.ListenAndServe(addr, nil); err != nil {
			panic(err)
		}
	}()

	// Несколько CPU workers = нагрузка заметнее и стабильнее
	n := runtime.NumCPU()
	if n > 4 {
		n = 4
	}
	for i := 0; i < n; i++ {
		go cpuWorker(i)
	}

	go memoryWorker()
	go goroutineWorker()

	select {}
}
