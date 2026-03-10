import React, { FC, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Autocomplete,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    FormControl,
    MenuItem,
    Select,
    Stack,
    TextField,
    Typography,
} from '@mui/material';
import FilterAltIcon from '@mui/icons-material/FilterAlt';
import { getUrls } from '../app/utils';

interface DashboardDataset {
    id: number;
    name: string;
    schema: string;
    database: string;
    description: string;
    column_count: number;
    column_names: string[];
    row_count: number | null;
}

interface DashboardFilterDefinition {
    id: string;
    name: string;
    filter_type: string;
    input_type: 'select' | 'text' | 'numeric' | 'time';
    dataset_id: number;
    dataset_name: string;
    column_name: string;
    column_type: string;
    multi: boolean;
    required: boolean;
    supports_search: boolean;
}

interface FilterOption {
    label: string;
    value: string | number | boolean | null;
}

export interface DashboardFilterPayload {
    column: string;
    operator: string;
    value?: string | number | boolean | Array<string | number | boolean> | [string | number, string | number];
}

interface FilterFormValue {
    operator: string;
    value: string | number | boolean | Array<string | number | boolean>;
    valueTo?: string;
}

interface SupersetDashboardFilterDialogProps {
    open: boolean;
    dashboardId: number;
    dashboardTitle: string;
    dataset: DashboardDataset | null;
    onClose: () => void;
    onSubmit: (filters: DashboardFilterPayload[], tableNameOverride?: string) => Promise<void>;
}

const defaultOperatorForFilter = (filter: DashboardFilterDefinition) => {
    if (filter.input_type === 'time') return 'BETWEEN';
    if (filter.input_type === 'numeric') return 'EQ';
    if (filter.input_type === 'select') return filter.multi ? 'IN' : 'EQ';
    return 'ILIKE';
};

const isEmptyValue = (value: FilterFormValue | undefined, inputType: DashboardFilterDefinition['input_type']) => {
    if (!value) return true;
    if (inputType === 'select') {
        return Array.isArray(value.value) ? value.value.length === 0 : value.value === '' || value.value == null;
    }
    if (value.operator === 'IS_NULL' || value.operator === 'IS_NOT_NULL') return false;
    if (value.operator === 'BETWEEN') {
        return value.value === '' || value.value == null || value.valueTo === '' || value.valueTo == null;
    }
    return value.value === '' || value.value == null;
};

const normalizeNumericValue = (value: string) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : value;
};

export const SupersetDashboardFilterDialog: FC<SupersetDashboardFilterDialogProps> = ({
    open,
    dashboardId,
    dashboardTitle,
    dataset,
    onClose,
    onSubmit,
}) => {
    const [loading, setLoading] = useState(false);
    const [submitLoading, setSubmitLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [filters, setFilters] = useState<DashboardFilterDefinition[]>([]);
    const [formValues, setFormValues] = useState<Record<string, FilterFormValue>>({});
    const [suffixInput, setSuffixInput] = useState('');
    const [suffixManuallyEdited, setSuffixManuallyEdited] = useState(false);
    const [optionsMap, setOptionsMap] = useState<Record<string, FilterOption[]>>({});
    const [optionsMoreMap, setOptionsMoreMap] = useState<Record<string, boolean>>({});
    const [optionSearchMap, setOptionSearchMap] = useState<Record<string, string>>({});
    const [optionsLoadingKey, setOptionsLoadingKey] = useState<string | null>(null);
    const searchTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

    const buildAutoSuffix = useCallback(() => {
        const parts: string[] = [];
        for (const filter of filters) {
            const fv = formValues[filter.id];
            if (isEmptyValue(fv, filter.input_type)) continue;
            let valStr: string;
            if (fv.operator === 'IS_NULL') valStr = 'null';
            else if (fv.operator === 'IS_NOT_NULL') valStr = 'notnull';
            else if (Array.isArray(fv.value)) valStr = fv.value.slice(0, 3).map(String).join('_');
            else valStr = String(fv.value);
            valStr = valStr.replace(/[^a-zA-Z0-9\u4e00-\u9fff_-]/g, '_').replace(/_+/g, '_').slice(0, 20);
            parts.push(valStr);
        }
        if (parts.length === 0) {
            const d = new Date();
            return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
        }
        return parts.join('_');
    }, [filters, formValues]);

    useEffect(() => {
        if (!suffixManuallyEdited) {
            setSuffixInput(buildAutoSuffix());
        }
    }, [buildAutoSuffix, suffixManuallyEdited]);

    useEffect(() => {
        if (!open || !dataset) return;

        const fetchFilters = async () => {
            setLoading(true);
            setError(null);
            setFilters([]);
            setFormValues({});
            setOptionsMap({});
            setOptionsMoreMap({});
            setOptionSearchMap({});
            setSuffixInput('');
            setSuffixManuallyEdited(false);
            try {
                const url = `${getUrls().SUPERSET_DASHBOARD_FILTERS}/${dashboardId}/filters?dataset_id=${dataset.id}`;
                const resp = await fetch(url, { credentials: 'include' });
                const data = await resp.json();
                if (!resp.ok || data.status !== 'ok') {
                    throw new Error(data.message || `Server error (${resp.status})`);
                }
                const nextFilters = (data.filters || []) as DashboardFilterDefinition[];
                setFilters(nextFilters);
                setFormValues(
                    Object.fromEntries(
                        nextFilters.map(filter => [
                            filter.id,
                            {
                                operator: defaultOperatorForFilter(filter),
                                value: filter.multi ? [] : '',
                                valueTo: '',
                            },
                        ]),
                    ),
                );
            } catch (err: any) {
                setError(err.message || 'Failed to load dashboard filters');
            } finally {
                setLoading(false);
            }
        };

        fetchFilters();
        return () => {
            Object.values(searchTimersRef.current).forEach(clearTimeout);
            searchTimersRef.current = {};
        };
    }, [open, dashboardId, dataset]);

    const loadOptions = async (filter: DashboardFilterDefinition, keyword = '') => {
        if (filter.input_type !== 'select') return;
        setOptionsLoadingKey(filter.id);
        try {
            const params = new URLSearchParams({
                dataset_id: String(filter.dataset_id),
                column_name: filter.column_name,
                limit: '50',
            });
            if (keyword.trim()) {
                params.set('keyword', keyword.trim());
            }
            const resp = await fetch(`${getUrls().SUPERSET_FILTER_OPTIONS}?${params.toString()}`, {
                credentials: 'include',
            });
            const data = await resp.json();
            if (!resp.ok || data.status !== 'ok') {
                throw new Error(data.message || `Server error (${resp.status})`);
            }
            setOptionsMap(prev => ({ ...prev, [filter.id]: data.options || [] }));
            setOptionsMoreMap(prev => ({ ...prev, [filter.id]: !!data.has_more }));
        } catch (err: any) {
            setError(err.message || 'Failed to load filter options');
        } finally {
            setOptionsLoadingKey((current) => (current === filter.id ? null : current));
        }
    };

    const queueOptionsLoad = (filter: DashboardFilterDefinition, keyword = '') => {
        if (searchTimersRef.current[filter.id]) {
            clearTimeout(searchTimersRef.current[filter.id]);
        }
        searchTimersRef.current[filter.id] = setTimeout(() => {
            loadOptions(filter, keyword);
        }, keyword ? 300 : 0);
    };

    const handleValueChange = (filterId: string, patch: Partial<FilterFormValue>) => {
        setFormValues(prev => ({
            ...prev,
            [filterId]: {
                ...prev[filterId],
                ...patch,
            },
        }));
    };

    const buildPayload = useMemo(() => {
        return (): DashboardFilterPayload[] => {
            return filters.flatMap((filter) => {
                const value = formValues[filter.id];
                if (isEmptyValue(value, filter.input_type)) {
                    return [];
                }
                if (value.operator === 'IS_NULL' || value.operator === 'IS_NOT_NULL') {
                    return [{ column: filter.column_name, operator: value.operator }];
                }
                if (filter.input_type === 'numeric') {
                    if (value.operator === 'BETWEEN') {
                        return [{
                            column: filter.column_name,
                            operator: value.operator,
                            value: [
                                normalizeNumericValue(String(value.value)),
                                normalizeNumericValue(String(value.valueTo ?? '')),
                            ],
                        }];
                    }
                    return [{
                        column: filter.column_name,
                        operator: value.operator,
                        value: normalizeNumericValue(String(value.value)),
                    }];
                }
                if (filter.input_type === 'time' && value.operator === 'BETWEEN') {
                    return [{
                        column: filter.column_name,
                        operator: value.operator,
                        value: [String(value.value), String(value.valueTo ?? '')],
                    }];
                }
                return [{
                    column: filter.column_name,
                    operator: value.operator,
                    value: value.value as DashboardFilterPayload['value'],
                }];
            });
        };
    }, [filters, formValues]);

    const getSelectedOptions = (filter: DashboardFilterDefinition) => {
        const selected = formValues[filter.id]?.value;
        const options = optionsMap[filter.id] || [];
        const asOption = (raw: string | number | boolean) => {
            const found = options.find(opt => String(opt.value) === String(raw));
            return found || { label: String(raw), value: raw };
        };
        if (filter.multi) {
            return Array.isArray(selected) ? selected.map(asOption) : [];
        }
        if (selected === '' || selected == null || Array.isArray(selected)) {
            return null;
        }
        return asOption(selected);
    };

    const handleSubmit = async () => {
        try {
            setSubmitLoading(true);
            setError(null);
            const fullName = suffixInput.trim()
                ? `${dataset?.name ?? ''}_${suffixInput.trim()}`
                : undefined;
            await onSubmit(buildPayload(), fullName);
            onClose();
        } catch (err: any) {
            setError(err.message || 'Failed to load dataset with filters');
        } finally {
            setSubmitLoading(false);
        }
    };

    const renderOperatorControl = (filter: DashboardFilterDefinition) => {
        const value = formValues[filter.id];
        let options: Array<{ value: string; label: string }> = [];
        if (filter.input_type === 'select') {
            options = filter.multi
                ? [{ value: 'IN', label: '包含任一值' }, { value: 'NOT_IN', label: '不包含这些值' }]
                : [{ value: 'EQ', label: '等于' }, { value: 'NEQ', label: '不等于' }];
        } else if (filter.input_type === 'numeric') {
            options = [
                { value: 'EQ', label: '等于' },
                { value: 'GT', label: '大于' },
                { value: 'GTE', label: '大于等于' },
                { value: 'LT', label: '小于' },
                { value: 'LTE', label: '小于等于' },
                { value: 'BETWEEN', label: '介于' },
                { value: 'IS_NULL', label: '为空' },
                { value: 'IS_NOT_NULL', label: '非空' },
            ];
        } else if (filter.input_type === 'time') {
            options = [
                { value: 'BETWEEN', label: '时间范围' },
                { value: 'EQ', label: '等于' },
                { value: 'IS_NULL', label: '为空' },
                { value: 'IS_NOT_NULL', label: '非空' },
            ];
        } else {
            options = [
                { value: 'ILIKE', label: '包含' },
                { value: 'EQ', label: '等于' },
                { value: 'NEQ', label: '不等于' },
                { value: 'IS_NULL', label: '为空' },
                { value: 'IS_NOT_NULL', label: '非空' },
            ];
        }

        return (
            <FormControl size="small" sx={{ minWidth: 100 }}>
                <Select
                    value={value?.operator || defaultOperatorForFilter(filter)}
                    onChange={(e) => handleValueChange(filter.id, { operator: e.target.value })}
                    sx={{ fontSize: 12, '& .MuiSelect-select': { py: 0.625 } }}
                >
                    {options.map(option => (
                        <MenuItem key={option.value} value={option.value} sx={{ fontSize: 12 }}>
                            {option.label}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>
        );
    };

    const renderValueControl = (filter: DashboardFilterDefinition) => {
        const formValue = formValues[filter.id];
        const operator = formValue?.operator || defaultOperatorForFilter(filter);
        if (operator === 'IS_NULL' || operator === 'IS_NOT_NULL') {
            return (
                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 11 }}>
                    此操作无需填写值
                </Typography>
            );
        }

        if (filter.input_type === 'select') {
            return (
                <Box sx={{ flex: 1 }}>
                    <Autocomplete
                        multiple={filter.multi}
                        size="small"
                        options={optionsMap[filter.id] || []}
                        value={getSelectedOptions(filter) as any}
                        loading={optionsLoadingKey === filter.id}
                        filterOptions={(options) => options}
                        isOptionEqualToValue={(option, value) => String(option.value) === String(value.value)}
                        getOptionLabel={(option) => option.label}
                        onOpen={() => {
                            if (!optionsMap[filter.id]) {
                                queueOptionsLoad(filter, '');
                            }
                        }}
                        onChange={(_, value) => {
                            handleValueChange(filter.id, {
                                value: filter.multi
                                    ? (value as FilterOption[]).map(item => item.value).filter(item => item != null) as Array<string | number | boolean>
                                    : ((value as FilterOption | null)?.value ?? ''),
                            });
                            setOptionSearchMap(prev => ({ ...prev, [filter.id]: '' }));
                        }}
                        inputValue={optionSearchMap[filter.id] || ''}
                        onInputChange={(_, value, reason) => {
                            if (reason === 'input') {
                                setOptionSearchMap(prev => ({ ...prev, [filter.id]: value }));
                                queueOptionsLoad(filter, value);
                            }
                        }}
                        slotProps={{
                            listbox: { sx: { fontSize: 12 } },
                            chip: { size: 'small', sx: { fontSize: 11, height: 20 } },
                        }}
                        renderInput={(params) => (
                            <TextField
                                {...params}
                                size="small"
                                placeholder={filter.supports_search ? '读取候选值，可搜索' : '选择值'}
                                sx={{ '& .MuiOutlinedInput-root': { fontSize: 12 } }}
                            />
                        )}
                    />
                    {optionsMoreMap[filter.id] && (
                        <Typography variant="caption" sx={{ color: 'text.secondary', mt: 0.25, display: 'block', fontSize: 10 }}>
                            结果已截断，输入关键字缩小范围
                        </Typography>
                    )}
                </Box>
            );
        }

        const inputSx = { '& .MuiOutlinedInput-root': { fontSize: 12, '& input': { py: 0.75 } } };

        if (filter.input_type === 'time') {
            return (
                <Stack direction="row" spacing={0.75} sx={{ flex: 1 }}>
                    <TextField
                        size="small"
                        type="date"
                        value={String(formValue?.value || '')}
                        onChange={(e) => handleValueChange(filter.id, { value: e.target.value })}
                        InputLabelProps={{ shrink: true }}
                        sx={{ flex: 1, ...inputSx }}
                    />
                    {operator === 'BETWEEN' && (
                        <TextField
                            size="small"
                            type="date"
                            value={formValue?.valueTo || ''}
                            onChange={(e) => handleValueChange(filter.id, { valueTo: e.target.value })}
                            InputLabelProps={{ shrink: true }}
                            sx={{ flex: 1, ...inputSx }}
                        />
                    )}
                </Stack>
            );
        }

        if (filter.input_type === 'numeric') {
            return (
                <Stack direction="row" spacing={0.75} sx={{ flex: 1 }}>
                    <TextField
                        size="small"
                        type="number"
                        value={String(formValue?.value || '')}
                        onChange={(e) => handleValueChange(filter.id, { value: e.target.value })}
                        placeholder="值"
                        sx={{ flex: 1, ...inputSx }}
                    />
                    {operator === 'BETWEEN' && (
                        <TextField
                            size="small"
                            type="number"
                            value={formValue?.valueTo || ''}
                            onChange={(e) => handleValueChange(filter.id, { valueTo: e.target.value })}
                            placeholder="结束值"
                            sx={{ flex: 1, ...inputSx }}
                        />
                    )}
                </Stack>
            );
        }

        return (
            <TextField
                size="small"
                value={String(formValue?.value || '')}
                onChange={(e) => handleValueChange(filter.id, { value: e.target.value })}
                placeholder="输入筛选内容"
                sx={{ flex: 1, ...inputSx }}
            />
        );
    };

    return (
        <Dialog
            open={open}
            onClose={submitLoading ? undefined : onClose}
            fullWidth
            maxWidth="sm"
            PaperProps={{ sx: { borderRadius: 2 } }}
        >
            <DialogTitle sx={{ fontSize: 14, fontWeight: 600, pb: 0.5, pt: 2, px: 2.5, display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
                <FilterAltIcon sx={{ fontSize: 16, color: 'text.secondary', mt: 0.25 }} />
                <Box sx={{ minWidth: 0 }}>
                    <Box sx={{ fontSize: 14, fontWeight: 600, lineHeight: 1.4 }}>按条件加载</Box>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 11, lineHeight: 1.3 }}>
                        {dashboardTitle} / {dataset?.name ?? ''}
                    </Typography>
                </Box>
            </DialogTitle>
            <DialogContent sx={{ px: 2.5, pt: 1 }}>
                <Stack spacing={1.5}>
                    <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: 11, lineHeight: 1.5 }}>
                        读取该仪表盘允许的筛选项，不包含仪表盘当前已选中的条件。留空的筛选项不会生效。
                    </Typography>

                    {error && <Alert severity="error" sx={{ fontSize: 12, py: 0.25 }} onClose={() => setError(null)}>{error}</Alert>}

                    <Box>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, color: 'text.secondary', fontWeight: 500 }}>
                        将要导入的表名
                        </Typography>
                        <Box sx={{
                            display: 'flex', alignItems: 'center', gap: 0,
                            border: '1px solid', borderColor: 'divider', borderRadius: 1,
                            overflow: 'hidden',
                        }}>
                            <Typography variant="body2" sx={{
                                fontSize: 13, color: 'text.secondary', whiteSpace: 'nowrap',
                                px: 1.5, py: 0.75, bgcolor: 'action.hover', borderRight: '1px solid', borderColor: 'divider',
                            }}>
                                {dataset?.name ?? ''}_
                            </Typography>
                            <TextField
                                autoFocus
                                size="small"
                                fullWidth
                                variant="standard"
                                placeholder="根据条件自动生成"
                                value={suffixInput}
                                onChange={(e) => {
                                    setSuffixInput(e.target.value);
                                    setSuffixManuallyEdited(true);
                                }}
                                slotProps={{ input: { disableUnderline: true, sx: { fontSize: 13, px: 1, py: 0.75 } } }}
                            />
                        </Box>
                        {suffixInput.trim() && (
                            <Chip
                                size="small"
                                variant="outlined"
                                color="primary"
                                label={`${dataset?.name ?? ''}_${suffixInput.trim()}`}
                                sx={{ mt: 0.75, fontSize: 11, height: 22 }}
                            />
                        )}
                    </Box>

                    <Divider />

                    {loading ? (
                        <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
                            <CircularProgress size={20} />
                        </Box>
                    ) : filters.length === 0 ? (
                        <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: 12, textAlign: 'center', py: 2 }}>
                            当前仪表盘没有识别到可用于该数据集的筛选项，将按原始数据集直接加载。
                        </Typography>
                    ) : (
                        <Stack spacing={1}>
                            {filters.map((filter) => (
                                <Box
                                    key={`${filter.id}-${filter.column_name}`}
                                    sx={{
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        borderRadius: 1,
                                        px: 1.5,
                                        py: 1,
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.75, flexWrap: 'wrap' }}>
                                        <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 12 }}>
                                            {filter.name}
                                        </Typography>
                                        <Chip size="small" variant="outlined" label={filter.column_name} sx={{ fontSize: 10, height: 18, color: 'text.secondary', borderColor: 'divider' }} />
                                        <Chip size="small" variant="outlined" label={filter.column_type} sx={{ fontSize: 10, height: 18, color: 'text.secondary', borderColor: 'divider' }} />
                                        {filter.multi && <Chip size="small" color="primary" variant="outlined" label="多选" sx={{ fontSize: 10, height: 18 }} />}
                                    </Box>
                                    <Stack direction="row" spacing={0.75} alignItems="center">
                                        {renderOperatorControl(filter)}
                                        {renderValueControl(filter)}
                                    </Stack>
                                </Box>
                            ))}
                        </Stack>
                    )}
                </Stack>
            </DialogContent>
            <DialogActions sx={{ px: 2.5, pb: 2, pt: 0.5 }}>
                <Button onClick={onClose} disabled={submitLoading} size="small" sx={{ textTransform: 'none', fontSize: 12 }}>
                    取消
                </Button>
                <Button
                    variant="contained"
                    size="small"
                    disableElevation
                    onClick={handleSubmit}
                    disabled={loading || submitLoading || !dataset}
                    startIcon={submitLoading ? <CircularProgress size={12} /> : undefined}
                    sx={{ textTransform: 'none', fontSize: 12 }}
                >
                    加载数据
                </Button>
            </DialogActions>
        </Dialog>
    );
};

