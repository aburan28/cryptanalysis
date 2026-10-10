"""Add observation-only phase clocks to the frozen round110 continuation."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent/'round110/seeded.cpp'


def once(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new, 1)


def generate():
    source = SOURCE.read_text()
    source = once(source, '#include "seeded.h"', '#include "seeded.h"\n#include "phase.h"')
    source = once(source, 'using Clock = std::chrono::steady_clock;', '''using Clock = std::chrono::steady_clock;
thread_local SeededPhaseStats seeded_phases{};

struct PhaseClock {
    Clock::time_point last = Clock::now();
    uint32_t stage = 0;
    void mark(uint32_t next) {
        const auto now = Clock::now();
        uint64_t elapsed_ns = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
            now - last).count());
        uint64_t *slots[] = {&seeded_phases.preparation_ns, &seeded_phases.f4_ns,
                             &seeded_phases.packing_ns, &seeded_phases.composition_ns,
                             &seeded_phases.finalization_ns};
        if (stage < 5) *slots[stage] += elapsed_ns;
        seeded_phases.stage_at_exit = stage;
        stage = next;
        last = now;
    }
    void finish() {
        mark(5);
        seeded_phases.total_ns = seeded_phases.preparation_ns + seeded_phases.f4_ns +
            seeded_phases.packing_ns + seeded_phases.composition_ns +
            seeded_phases.finalization_ns;
        seeded_phases.completed = 1;
    }
};''')
    source = once(source, 'const char *seeded_error() { return failure.c_str(); }',
        'const SeededPhaseStats *seeded_last_phases() { return &seeded_phases; }\n'
        'const char *seeded_error() { return failure.c_str(); }')
    prefix, function = source.split('void *seeded_produce(', 1)
    function = once(function, '    auto start = Clock::now();',
        '    auto start = Clock::now();\n    seeded_phases = {};\n    PhaseClock phase_clock;')
    function = once(function, '        failure = "null seeded stats";\n        return nullptr;',
        '        failure = "null seeded stats";\n        phase_clock.finish();\n        return nullptr;')
    function = once(function, '        stats->f4_started = 1;',
        '        phase_clock.mark(1);\n        stats->f4_started = 1;')
    function = once(function, '        remaining -= engine->work;',
        '        remaining -= engine->work;\n        phase_clock.mark(2);')
    function = once(function, '        stats->composition_started = 1;',
        '        phase_clock.mark(3);\n        stats->composition_started = 1;')
    function = once(function, '        remaining -= stats->composition.work;',
        '        remaining -= stats->composition.work;\n        phase_clock.mark(4);')
    assert function.count('    } catch (') == 4
    # Charge exception handling and status export to finalization. The caught
    # stage still contains all attempted F4 or composition work.
    function = function.replace('    } catch (const Budget &e) {',
        '    } catch (const Budget &e) {\n        phase_clock.mark(4);', 1)
    function = function.replace('    } catch (const std::invalid_argument &e) {',
        '    } catch (const std::invalid_argument &e) {\n        phase_clock.mark(4);', 1)
    function = function.replace('    } catch (const std::exception &e) {',
        '    } catch (const std::exception &e) {\n        phase_clock.mark(4);', 1)
    function = function.replace('    } catch (...) {',
        '    } catch (...) {\n        phase_clock.mark(4);', 1)
    success = '        stats->total_seconds = std::chrono::duration<double>(Clock::now() - start).count();\n        return result.release();'
    function = once(function, success, '        phase_clock.finish();\n' + success)
    failure = '    stats->total_seconds = std::chrono::duration<double>(Clock::now() - start).count();\n    return nullptr;'
    function = once(function, failure, '    phase_clock.finish();\n' + failure)
    return prefix + 'void *seeded_produce(' + function


if __name__ == '__main__':
    target = HERE/'build/seeded_phases.cpp'
    target.parent.mkdir(exist_ok=True)
    target.write_text(generate())
    print(target)
