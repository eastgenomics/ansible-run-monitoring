# Running Test

The following command will run all tests within test directory

```
docker build -t ansible:test -f Dockerfile.test .

docker run --env-file /path/to/env/file ansible:test
```