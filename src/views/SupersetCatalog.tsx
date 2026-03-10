// Superset Dataset Catalog panel for Data Formulator.
// Follows the same MUI + Fluent-style conventions as DBTableManager.

import React, { FC, useState, useEffect, useCallback } from 'react';
import {
    Box,
    Typography,
    Button,
    TextField,
    CircularProgress,
    IconButton,
    Tooltip,
    Chip,
    Paper,
    Divider,
    Alert,
    useTheme,
    alpha,
    InputAdornment,
    LinearProgress,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from '@mui/material';
import StorageIcon from '@mui/icons-material/Storage';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import AddIcon from '@mui/icons-material/Add';
import TableRowsIcon from '@mui/icons-material/TableRows';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { DataFormulatorState } from '../app/dfSlice';
import { getUrls } from '../app/utils';

interface SupersetDataset {
    id: number;
    name: string;
    schema: string;
    database: string;
    description: string;
    column_count: number;
    column_names: string[];
    row_count: number | null;
}

interface SupersetCatalogProps {
    onDatasetLoaded?: (tableName: string, rowCount: number) => void;
}

const MAX_COLUMN_DISPLAY = 60;
const MAX_TOOLTIP_ROWS = 12;

const ColumnChip: FC<{ columns: string[] }> = ({ columns }) => {
    const { t } = useTranslation();
    const joined = columns.join(', ');
    const truncated = joined.length > MAX_COLUMN_DISPLAY;
    const display = truncated ? joined.slice(0, MAX_COLUMN_DISPLAY) + '…' : joined;

    const chip = (
        <Chip
            size="small"
            variant="outlined"
            label={`${t('supersetCatalog.columns', { count: columns.length })}: ${display}`}
            sx={{
                fontSize: 10,
                height: 'auto',
                minHeight: 18,
                color: 'text.secondary',
                borderColor: 'divider',
                '& .MuiChip-label': {
                    whiteSpace: 'normal',
                    lineHeight: 1.3,
                    py: 0.25,
                },
                maxWidth: '100%',
            }}
        />
    );

    return (
        <Tooltip
            title={
                <Box
                    sx={{
                        maxWidth: 520,
                        display: 'grid',
                        gridAutoFlow: 'column',
                        gridTemplateRows: `repeat(${MAX_TOOLTIP_ROWS}, minmax(0, auto))`,
                        gridAutoColumns: 'minmax(140px, max-content)',
                        columnGap: 1.5,
                        rowGap: 0.25,
                        alignItems: 'start',
                        fontSize: 11,
                        lineHeight: 1.6,
                    }}
                >
                    {columns.map((col, i) => (
                        <Box
                            key={i}
                            sx={{
                                minWidth: 0,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                            }}
                        >
                            {col}
                        </Box>
                    ))}
                </Box>
            }
            placement="top"
            arrow
        >
            {chip}
        </Tooltip>
    );
};

export const SupersetCatalog: FC<SupersetCatalogProps> = ({ onDatasetLoaded }) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const serverConfig = useSelector((state: DataFormulatorState) => state.serverConfig);

    const [datasets, setDatasets] = useState<SupersetDataset[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [loadingDatasetId, setLoadingDatasetId] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [suffixDialogOpen, setSuffixDialogOpen] = useState(false);
    const [suffixDialogDs, setSuffixDialogDs] = useState<SupersetDataset | null>(null);
    const [suffixInput, setSuffixInput] = useState('');

    const fetchDatasets = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const resp = await fetch(getUrls().SUPERSET_CATALOG_DATASETS, {
                credentials: 'include',
            });
            if (!resp.ok) {
                const text = await resp.text();
                try {
                    const errData = JSON.parse(text);
                    setError(errData.message || `Server error (${resp.status})`);
                } catch {
                    setError(`Server error (${resp.status})`);
                }
                return;
            }
            const data = await resp.json();
            if (data.status === 'ok') {
                setDatasets(data.datasets || []);
            } else {
                setError(data.message || 'Failed to load datasets');
            }
        } catch (err: any) {
            setError(err.message || 'Network error');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (serverConfig.SUPERSET_ENABLED && serverConfig.AUTH_USER) {
            fetchDatasets();
        }
    }, [serverConfig.SUPERSET_ENABLED, serverConfig.AUTH_USER]);

    const loadDataset = async (dataset: SupersetDataset, tableNameOverride?: string) => {
        setLoadingDatasetId(dataset.id);
        setError(null);
        setSuccessMessage(null);
        try {
            const body: Record<string, any> = {
                dataset_id: dataset.id,
                row_limit: 20000,
            };
            if (tableNameOverride) body.table_name = tableNameOverride;

            const resp = await fetch(getUrls().SUPERSET_LOAD_DATASET, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!resp.ok) {
                const text = await resp.text();
                try {
                    const errData = JSON.parse(text);
                    throw new Error(errData.message || `Server error (${resp.status})`);
                } catch (parseErr: any) {
                    if (parseErr.message.includes('Server error') || parseErr.message.includes('Superset'))
                        throw parseErr;
                    throw new Error(`Server error (${resp.status})`);
                }
            }
            const data = await resp.json();
            if (data.status === 'ok') {
                setSuccessMessage(t('supersetCatalog.loadSuccess', {
                    name: tableNameOverride || dataset.name,
                    count: data.row_count,
                }));
                onDatasetLoaded?.(data.table_name, data.row_count);
            } else {
                setError(t('supersetCatalog.loadFailed', { message: data.message }));
            }
        } catch (err: any) {
            setError(t('supersetCatalog.loadFailed', { message: err.message }));
        } finally {
            setLoadingDatasetId(null);
        }
    };

    const filteredDatasets = datasets.filter(ds => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return (
            (ds.name ?? '').toLowerCase().includes(q) ||
            (ds.database ?? '').toLowerCase().includes(q) ||
            (ds.schema ?? '').toLowerCase().includes(q) ||
            (ds.description ?? '').toLowerCase().includes(q) ||
            (ds.column_names ?? []).some(c => (c ?? '').toLowerCase().includes(q))
        );
    });

    if (!serverConfig.SUPERSET_ENABLED || !serverConfig.AUTH_USER) {
        return null;
    }

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 1 }}>
                <StorageIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, flex: 1 }}>
                    {t('supersetCatalog.title')}
                </Typography>
                <Tooltip title={t('supersetCatalog.refresh')}>
                    <IconButton size="small" onClick={fetchDatasets} disabled={loading}>
                        <RefreshIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
            </Box>

            <Divider />

            <Box sx={{ px: 1.5, py: 1 }}>
                <TextField
                    size="small"
                    placeholder={t('supersetCatalog.searchPlaceholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    fullWidth
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            </InputAdornment>
                        ),
                    }}
                    sx={{ '& .MuiOutlinedInput-root': { fontSize: 13 } }}
                />
            </Box>

            {error && (
                <Alert severity="error" sx={{ mx: 1.5, fontSize: 12 }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}
            {successMessage && (
                <Alert severity="success" sx={{ mx: 1.5, fontSize: 12 }} onClose={() => setSuccessMessage(null)}>
                    {successMessage}
                </Alert>
            )}

            {loading && <LinearProgress sx={{ mx: 1.5 }} />}

            <Box sx={{ flex: 1, overflowY: 'auto', px: 1, py: 0.5 }}>
                {!loading && filteredDatasets.length === 0 && (
                    <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mt: 3, fontSize: 13 }}>
                        {t('supersetCatalog.noDatasets')}
                    </Typography>
                )}

                {filteredDatasets.map((ds) => (
                    <Paper
                        key={ds.id}
                        variant="outlined"
                        sx={{
                            p: 1.5,
                            mb: 1,
                            cursor: 'default',
                            borderColor: alpha(theme.palette.divider, 0.15),
                            '&:hover': {
                                borderColor: theme.palette.primary.main,
                                backgroundColor: alpha(theme.palette.primary.main, 0.02),
                            },
                        }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <TableRowsIcon sx={{ fontSize: 16, color: 'primary.main', flexShrink: 0 }} />
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontWeight: 600,
                                            fontSize: 13,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap',
                                        }}
                                    >
                                        {ds.name}
                                    </Typography>
                                </Box>
                                {ds.description && (
                                    <Tooltip title={ds.description.length > 80 ? ds.description : ''} placement="top" arrow>
                                        <Typography
                                            variant="caption"
                                            sx={{
                                                color: 'text.secondary',
                                                display: '-webkit-box',
                                                WebkitLineClamp: 2,
                                                WebkitBoxOrient: 'vertical',
                                                overflow: 'hidden',
                                                mt: 0.25,
                                                lineHeight: 1.4,
                                            }}
                                        >
                                            {ds.description}
                                        </Typography>
                                    </Tooltip>
                                )}
                                <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                                    <Typography variant="caption" sx={{ fontSize: 10, color: 'text.secondary' }}>
                                        {`${ds.database}.${ds.schema}`}
                                    </Typography>
                                    {ds.row_count != null && (
                                        <Chip
                                            size="small"
                                            variant="outlined"
                                            label={t('supersetCatalog.rows', { count: ds.row_count })}
                                            sx={{ fontSize: 10, height: 18, color: 'text.secondary', borderColor: 'divider' }}
                                        />
                                    )}
                                </Box>
                                {ds.column_names.length > 0 && (
                                    <Box sx={{ mt: 0.5 }}>
                                        <ColumnChip columns={ds.column_names} />
                                    </Box>
                                )}
                            </Box>

                            <Box sx={{ display: 'flex', gap: 0.5, ml: 1, flexShrink: 0, alignSelf: 'center' }}>
                                <Tooltip title={t('supersetCatalog.loadOverwrite')}>
                                    <span>
                                        <IconButton
                                            size="small"
                                            onClick={() => loadDataset(ds)}
                                            disabled={loadingDatasetId === ds.id}
                                        >
                                            {loadingDatasetId === ds.id ? <CircularProgress size={14} /> : <DownloadIcon sx={{ fontSize: 16 }} />}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title={t('supersetCatalog.createNewDataset')}>
                                    <span>
                                        <IconButton
                                            size="small"
                                            onClick={() => {
                                                setSuffixDialogDs(ds);
                                                const d = new Date();
                                                const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
                                                setSuffixInput(ymd);
                                                setSuffixDialogOpen(true);
                                            }}
                                            disabled={loadingDatasetId === ds.id}
                                        >
                                            <AddIcon sx={{ fontSize: 16 }} />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Box>
                        </Box>
                    </Paper>
                ))}
            </Box>

            <Dialog
                open={suffixDialogOpen}
                onClose={() => setSuffixDialogOpen(false)}
                maxWidth="xs"
                fullWidth
                PaperProps={{ sx: { borderRadius: 2 } }}
            >
                <DialogTitle sx={{ fontSize: 14, fontWeight: 600, pb: 0.5, pt: 2, px: 2.5 }}>
                    {t('supersetCatalog.suffixDialogTitle')}
                </DialogTitle>
                <DialogContent sx={{ px: 2.5, pt: 1 }}>
                    <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary', fontSize: 12, lineHeight: 1.6 }}>
                        {t('supersetCatalog.suffixDialogDesc', { name: suffixDialogDs?.name ?? '' })}
                    </Typography>

                    <Typography variant="caption" sx={{ display: 'block', mb: 0.5, color: 'text.secondary', fontWeight: 500 }}>
                        {t('supersetCatalog.suffixPreview')}
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
                            {suffixDialogDs?.name ?? ''}_
                        </Typography>
                        <TextField
                            autoFocus
                            size="small"
                            fullWidth
                            variant="standard"
                            placeholder={t('supersetCatalog.suffixPlaceholder')}
                            value={suffixInput}
                            onChange={(e) => setSuffixInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && suffixInput.trim()) {
                                    const tableName = `${suffixDialogDs!.name}_${suffixInput.trim()}`;
                                    loadDataset(suffixDialogDs!, tableName);
                                    setSuffixDialogOpen(false);
                                }
                            }}
                            slotProps={{ input: { disableUnderline: true, sx: { fontSize: 13, px: 1, py: 0.75 } } }}
                        />
                    </Box>
                    {suffixInput.trim() && (
                        <Chip
                            size="small"
                            variant="outlined"
                            color="primary"
                            label={`${suffixDialogDs?.name}_${suffixInput.trim()}`}
                            sx={{ mt: 1, fontSize: 12, height: 24 }}
                        />
                    )}
                </DialogContent>
                <DialogActions sx={{ px: 2.5, pb: 2, pt: 0.5 }}>
                    <Button onClick={() => setSuffixDialogOpen(false)} size="small" sx={{ textTransform: 'none', fontSize: 12 }}>
                        {t('supersetCatalog.cancel')}
                    </Button>
                    <Button
                        variant="contained"
                        size="small"
                        disableElevation
                        disabled={!suffixInput.trim()}
                        onClick={() => {
                            const tableName = `${suffixDialogDs!.name}_${suffixInput.trim()}`;
                            loadDataset(suffixDialogDs!, tableName);
                            setSuffixDialogOpen(false);
                        }}
                        sx={{ textTransform: 'none', fontSize: 12 }}
                    >
                        {t('supersetCatalog.confirmLoad')}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
};
