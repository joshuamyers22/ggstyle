# Security policy

`ggstyle` is a local plotting library: it does not make network requests, execute input,
or deserialize untrusted objects. Treat custom matplotlib formatters and user-provided
callables as trusted Python code.

Please report a suspected vulnerability privately to `joshua.myers22@gmail.com` rather
than opening a public issue. Include the affected version, a minimal reproducer, and the
impact. Security fixes are made on the latest public release only.
