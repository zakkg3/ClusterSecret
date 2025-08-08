package util

func AppendMap[K comparable, V any](a, b map[K]V) map[K]V {
	if len(a) == 0 {
		return b
	}
	for k, v := range b {
		a[k] = v
	}
	return a
}
