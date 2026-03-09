// Tab container that groups SupersetCatalog (Datasets) and SupersetDashboards.
// Drop-in replacement for SupersetCatalog inside SplitDatabasePane.

import React, { FC, useState } from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import TableRowsIcon from '@mui/icons-material/TableRows';
import DashboardIcon from '@mui/icons-material/Dashboard';
import { useTranslation } from 'react-i18next';

import { SupersetCatalog } from './SupersetCatalog';
import { SupersetDashboards } from './SupersetDashboards';

interface SupersetPanelProps {
    onDatasetLoaded?: (tableName: string, rowCount: number) => void;
}

export const SupersetPanel: FC<SupersetPanelProps> = ({ onDatasetLoaded }) => {
    const { t } = useTranslation();
    const [tab, setTab] = useState<0 | 1>(0);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                variant="fullWidth"
                sx={{
                    minHeight: 36,
                    '& .MuiTab-root': { minHeight: 36, py: 0.5, textTransform: 'none', fontSize: 13 },
                }}
            >
                <Tab
                    icon={<DashboardIcon sx={{ fontSize: 16 }} />}
                    iconPosition="start"
                    label={t('supersetPanel.dashboards', 'Dashboards')}
                />
                <Tab
                    icon={<TableRowsIcon sx={{ fontSize: 16 }} />}
                    iconPosition="start"
                    label={t('supersetPanel.datasets', 'Datasets')}
                />
            </Tabs>

            <Box sx={{ flex: 1, overflow: 'hidden' }}>
                <Box sx={{ display: tab === 0 ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
                    <SupersetDashboards onDatasetLoaded={onDatasetLoaded} />
                </Box>
                <Box sx={{ display: tab === 1 ? 'flex' : 'none', flexDirection: 'column', height: '100%' }}>
                    <SupersetCatalog onDatasetLoaded={onDatasetLoaded} />
                </Box>
            </Box>
        </Box>
    );
};
