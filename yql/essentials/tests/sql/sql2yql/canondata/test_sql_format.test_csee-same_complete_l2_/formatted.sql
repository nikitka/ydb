SELECT
    AsList(
        ListMap(
            AsList(1, 2), ($x) -> {
                RETURN $x + Yql::Fold(
                    AsList(1), 0, ($a, $b) -> {
                        RETURN $a + $b;
                    }
                );
            }
        ),
        ListMap(
            AsList(10, 11), ($x) -> {
                RETURN $x + Yql::Fold(
                    AsList(1), 0, ($a, $b) -> {
                        RETURN $a + $b;
                    }
                );
            }
        )
    )
;
