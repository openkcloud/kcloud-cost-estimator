package main

import (
    "fmt"
    "log"
    "net/http"
)

func main() {
    http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
        fmt.Fprintf(w, `{"status":"healthy","service":"logger"}`)
    })
    
    log.Println("Logger service starting on :8007")
    if err := http.ListenAndServe(":8007", nil); err != nil {
        log.Fatal(err)
    }
}