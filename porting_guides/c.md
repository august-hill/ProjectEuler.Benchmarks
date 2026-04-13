# Porting Guide: Zig → C

## Template
```c
// Problem NNN: Title
// Description
// Answer: XXXXX

#include "../bench.h"

long long solve(void) {
    // solution
}

int main(void) {
    euler_bench(NNN, solve);
    return 0;
}
```

## Build
```bash
clang -O2 -Wall -o main_bench main.c -lm
```

## Key Translations
| Zig | C |
|-----|---|
| `@divTrunc(a,b)` | `a / b` |
| `@mod(a,b)` | `((a % b) + b) % b` (signed) |
| `@intCast(x)` | `(int64_t)x` |
| `@floatFromInt(x)` | `(double)x` |
| `for (0..n) \|i\|` | `for (int i=0; i<n; i++)` |
| `std.mem.zeroes([N]T)` | `memset(arr, 0, sizeof(arr))` |
| `std.math.sqrt(x)` | `sqrt(x)` |
| `comptime` blocks | Remove — compute at runtime |

## Gotchas
- No overflow trapping — C wraps silently
- `%` on negative numbers is implementation-defined — use the macro above
- Large arrays: stack is fine up to ~1MB, use `malloc` beyond
- File paths: relative, run from problem dir
