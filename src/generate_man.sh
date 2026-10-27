#!/usr/bin/env bash

destine_dir=$1

mkdir -p ${destine_dir}
cat > ${destine_dir}/spotify.1 <<"MAN"
.TH SPOTIFY 1 "December 2025" "Spotify Client" "User Commands"
.SH NAME
spotify \- Spotify streaming music client
.SH SYNOPSIS
.B spotify
[\fIOPTIONS\fR]
.SH DESCRIPTION
Spotify is a digital music service that gives you access to millions of songs.
.SH OPTIONS
.TP
\fB\-\-help\fR
Show help options
.TP
\fB\-\-debug\fR
Enable Spotify and Chromium diagnostics in the terminal.
.TP
\fB\-\-debug-log=FILE\fR
Enable diagnostics and append terminal output to a private log file.
.SH ENVIRONMENT
SPOTIFY_DEBUG=1 enables diagnostics. XDG_CONFIG_HOME selects the configuration directory.
.SH SEE ALSO
https://www.spotify.com/
MAN