# Development workflow

Rules for making code changes in this repo.

## Commits
- Keep commits atomic: each one is a single logical unit of work that could be cherry-picked or reverted on its own without breaking the tree.
- Don't bundle unrelated changes into one commit.

## Branching
- Create a separate branch for each feature or substantial chunk of work.
- Don't make large changes directly on `main`.

## Testing
- Write tests that verify the correctness of any implementation before considering it done.
- Only commit and submit for PR review after all tests pass.
- No test framework is set up yet. The first change that adds tests should introduce one (`pytest` is the natural choice given the codebase is Python) rather than each task picking its own approach.

## Comments
- Default to no comments.
- Add a comment only when the code itself doesn't explain the *why* — e.g. non-obvious math, a quirk of a library/API being called (see the geopy/Nominatim timeout gotcha in [Claude/geocodificacion_tiendas.md](Claude/geocodificacion_tiendas.md) as an example of the kind of thing worth a comment), or an assumption that isn't obvious from context.
