// Superset Dashboard browser panel for Data Formulator.
// Lets users pick a dashboard, then load datasets used by that dashboard.

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
    Collapse,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import AddIcon from '@mui/icons-material/Add';
import TableRowsIcon from '@mui/icons-material/TableRows';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import PersonIcon from '@mui/icons-material/Person';
import { useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import { DataFormulatorState } from '../app/dfSlice';
import { getUrls } from '../app/utils';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Dashboard {
    id: number;
    title: string;
    slug: string;
    status: string;
    url: string;
    changed_on_delta_humanized: string;
    owners: string[];
}

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

interface SupersetDashboardsProps {
    onDatasetLoaded?: (tableName: string, rowCount: number) => void;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const SupersetDashboards: FC<SupersetDashboardsProps> = ({ onDatasetLoaded }) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const serverConfig = useSelector((state: DataFormulatorState) => state.serverConfig);

    const [dashboards, setDashboards] = useState<Dashboard[]>([]);
    const [loading, setLoading] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const [expandedId, setExpandedId] = useState<number | null>(null);
    const [datasetsMap, setDatasetsMap] = useState<Record<number, DashboardDataset[]>>({});
    const [datasetsLoading, setDatasetsLoading] = useState<number | null>(null);

    const [loadingDatasetId, setLoadingDatasetId] = useState<number | null>(null);

    const [suffixDialogOpen, setSuffixDialogOpen] = useState(false);
    const [suffixDialogDs, setSuffixDialogDs] = useState<DashboardDataset | null>(null);
    const [suffixInput, setSuffixInput] = useState('');

    /* ---------- fetch dashboard list ---------- */

    const fetchDashboards = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const resp = await fetch(getUrls().SUPERSET_CATALOG_DASHBOARDS, {
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
                setDashboards(data.dashboards || []);
            } else {
                setError(data.message || 'Failed to load dashboards');
            }
        } catch (err: any) {
            setError(err.message || 'Network error');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (serverConfig.SUPERSET_ENABLED && serverConfig.AUTH_USER) {
            fetchDashboards();
        }
    }, [serverConfig.SUPERSET_ENABLED, serverConfig.AUTH_USER]);

    /* ---------- expand / collapse: fetch datasets for a dashboard ---------- */

    const toggleExpand = useCallback(async (dashboardId: number) => {
        if (expandedId === dashboardId) {
            setExpandedId(null);
            return;
        }
        setExpandedId(dashboardId);

        if (datasetsMap[dashboardId]) return;

        setDatasetsLoading(dashboardId);
        try {
            const resp = await fetch(
                `${getUrls().SUPERSET_DASHBOARD_DATASETS}/${dashboardId}/datasets`,
                { credentials: 'include' },
            );
            if (!resp.ok) throw new Error(`Server error (${resp.status})`);
            const data = await resp.json();
            if (data.status === 'ok') {
                setDatasetsMap(prev => ({ ...prev, [dashboardId]: data.datasets || [] }));
            } else {
                setError(data.message || 'Failed to load dashboard datasets');
            }
        } catch (err: any) {
            setError(err.message || 'Network error');
        } finally {
            setDatasetsLoading(null);
        }
    }, [expandedId, datasetsMap]);

    /* ---------- load a dataset (reuse existing endpoint) ---------- */

    const loadDataset = async (dataset: DashboardDataset, tableNameOverride?: string) => {
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

    /* ---------- filter ---------- */

    const filteredDashboards = dashboards.filter(db => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return (
            db.title.toLowerCase().includes(q) ||
            db.slug.toLowerCase().includes(q) ||
            db.owners.some(o => o.toLowerCase().includes(q))
        );
    });

    if (!serverConfig.SUPERSET_ENABLED || !serverConfig.AUTH_USER) {
        return null;
    }

    /* ---------- render ---------- */

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 1 }}>
                <DashboardIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, flex: 1 }}>
                    {t('supersetDashboard.title', 'Superset Dashboards')}
                </Typography>
                <Tooltip title={t('supersetCatalog.refresh')}>
                    <IconButton size="small" onClick={fetchDashboards} disabled={loading}>
                        <RefreshIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
            </Box>

            <Divider />

            {/* search */}
            <Box sx={{ px: 1.5, py: 1 }}>
                <TextField
                    size="small"
                    placeholder={t('supersetDashboard.searchPlaceholder', 'Search dashboards...')}
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

            {/* alerts */}
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

            {/* dashboard list */}
            <Box sx={{ flex: 1, overflowY: 'auto', px: 1, py: 0.5 }}>
                {!loading && filteredDashboards.length === 0 && (
                    <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center', mt: 3, fontSize: 13 }}>
                        {t('supersetDashboard.noDashboards', 'No dashboards found.')}
                    </Typography>
                )}

                {filteredDashboards.map((db) => {
                    const isExpanded = expandedId === db.id;
                    const datasets = datasetsMap[db.id];
                    const isLoadingDs = datasetsLoading === db.id;

                    return (
                        <Paper
                            key={db.id}
                            variant="outlined"
                            sx={{
                                mb: 1,
                                borderColor: isExpanded
                                    ? theme.palette.primary.main
                                    : alpha(theme.palette.divider, 0.15),
                                transition: 'border-color 0.15s',
                                '&:hover': {
                                    borderColor: theme.palette.primary.main,
                                    backgroundColor: alpha(theme.palette.primary.main, 0.02),
                                },
                            }}
                        >
                            {/* dashboard row */}
                            <Box
                                sx={{ display: 'flex', alignItems: 'center', p: 1.5, cursor: 'pointer' }}
                                onClick={() => toggleExpand(db.id)}
                            >
                                <DashboardIcon sx={{ fontSize: 16, color: 'primary.main', mr: 1, flexShrink: 0 }} />
                                <Box sx={{ flex: 1, minWidth: 0 }}>
                                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {db.title}
                                    </Typography>
                                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.25, flexWrap: 'wrap', alignItems: 'center' }}>
                                        {db.owners.length > 0 && (
                                            <Chip
                                                size="small"
                                                variant="outlined"
                                                icon={<PersonIcon sx={{ fontSize: '12px !important' }} />}
                                                label={db.owners.join(', ')}
                                                sx={{ fontSize: 10, height: 18, color: 'text.secondary', borderColor: 'divider' }}
                                            />
                                        )}
                                        {db.changed_on_delta_humanized && (
                                            <Typography variant="caption" sx={{ fontSize: 10, color: 'text.disabled' }}>
                                                {db.changed_on_delta_humanized}
                                            </Typography>
                                        )}
                                    </Box>
                                </Box>
                                {isExpanded ? <ExpandLessIcon sx={{ fontSize: 18, color: 'text.secondary' }} /> : <ExpandMoreIcon sx={{ fontSize: 18, color: 'text.secondary' }} />}
                            </Box>

                            {/* expanded dataset list */}
                            <Collapse in={isExpanded}>
                                <Divider />
                                <Box sx={{ px: 1.5, py: 1 }}>
                                    {isLoadingDs && <LinearProgress sx={{ mb: 1 }} />}
                                    {datasets && datasets.length === 0 && (
                                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                                            {t('supersetDashboard.noDatasetsInDashboard', 'No datasets in this dashboard.')}
                                        </Typography>
                                    )}
                                    {datasets && datasets.map((ds) => (
                                        <Box
                                            key={ds.id}
                                            sx={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                                py: 0.75,
                                                '&:not(:last-child)': { borderBottom: '1px solid', borderColor: 'divider' },
                                            }}
                                        >
                                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                                    <TableRowsIcon sx={{ fontSize: 14, color: 'text.secondary', flexShrink: 0 }} />
                                                    <Typography variant="body2" sx={{ fontSize: 12, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                        {ds.name}
                                                    </Typography>
                                                </Box>
                                                <Box sx={{ display: 'flex', gap: 0.5, mt: 0.25, alignItems: 'center' }}>
                                                    <Typography variant="caption" sx={{ fontSize: 10, color: 'text.disabled' }}>
                                                        {`${ds.database}.${ds.schema}`}
                                                    </Typography>
                                                    <Chip size="small" variant="outlined" label={t('supersetCatalog.columns', { count: ds.column_count })} sx={{ fontSize: 9, height: 16, color: 'text.disabled', borderColor: 'divider' }} />
                                                    {ds.row_count != null && (
                                                        <Chip size="small" variant="outlined" label={t('supersetCatalog.rows', { count: ds.row_count })} sx={{ fontSize: 9, height: 16, color: 'text.disabled', borderColor: 'divider' }} />
                                                    )}
                                                </Box>
                                            </Box>
                                            <Box sx={{ display: 'flex', gap: 0.5, ml: 1, flexShrink: 0 }}>
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
                                    ))}
                                </Box>
                            </Collapse>
                        </Paper>
                    );
                })}
            </Box>

            {/* suffix dialog (same pattern as SupersetCatalog) */}
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
