# Running Test

The following command will run all tests within test directory

```
docker build -t ansible:test -f Dockerfile.test .

docker run --env-file /path/to/env/file ansible:test

docker run --env-file <path to .env file> -v <path to /test/log/monitoring>:/log/monitoring -v <path to /test/genetics>:/genetics ansible:test /bin/bash -c "python -u mock.py && python -u main.py"

```