# Git merge baseline comparison

| Scenario | Git textual conflict | Return code |
|---|---:|---:|
| r1 | no | 0 |
| r2 | no | 0 |
| r3 | no | 0 |
| r4 | yes | 1 |
| r5 | yes | 1 |
| r6 | no | 0 |
| r7 | yes | 1 |
| n1 | yes | 1 |
| n2 | no | 0 |
| n3 | yes | 1 |
| n4 | yes | 1 |
| n5 | no | 0 |
| n6 | no | 0 |

## Raw outputs

### r1

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)

STDERR:

```

### r2

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 5 ++++-
 1 file changed, 4 insertions(+), 1 deletion(-)

STDERR:

```

### r3

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 4 ----
 1 file changed, 4 deletions(-)

STDERR:

```

### r4

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### r5

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### r6

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

STDERR:

```

### r7

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### n1

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### n2

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

STDERR:

```

### n3

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### n4

```text
STDOUT:
Auto-merging schema/schema.sql
CONFLICT (content): Merge conflict in schema/schema.sql
Automatic merge failed; fix conflicts and then commit the result.

STDERR:

```

### n5

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 6 ++++++
 1 file changed, 6 insertions(+)

STDERR:

```

### n6

```text
STDOUT:
Auto-merging schema/schema.sql
Merge made by the 'ort' strategy.
 schema/schema.sql | 3 ++-
 1 file changed, 2 insertions(+), 1 deletion(-)

STDERR:

```
