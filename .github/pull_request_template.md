## What this changes

<!-- One paragraph. What behaviour is different after this than before? -->

## Why

<!-- The bug, the measurement, or the request behind it. -->

## How it was verified

<!-- Tick what you actually ran locally.  CI runs all of it too, but a red
     pipeline costs a cycle. -->

- [ ] `ctest --test-dir build --output-on-failure`
- [ ] `clang-tidy -p build --quiet src/*.c tools/*.c tests/*.c`
- [ ] `cppcheck --enable=warning,performance,portability,style --inline-suppr --std=c11 --error-exitcode=1 --suppress=missingIncludeSystem -Iinclude -Isrc -Icuda src tools tests`
- [ ] Sanitizers: `-DCA_SANITIZE=address,undefined` and, for anything touching threads, `-DCA_SANITIZE=thread`
- [ ] `git-clang-format --diff <base>` is empty

## Algorithmic changes

<!-- Delete this section if the change is not algorithmic.  Otherwise: which
     reported constant moves, in which direction, and by how much?  The unit
     is S = group operations / sqrt(N); ca_bench prints it. -->

| benchmark | before | after |
|---|---|---|
|  |  |  |
