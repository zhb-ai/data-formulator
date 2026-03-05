// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React, { FC, useEffect, useRef, useState } from 'react';
import {
    Box,
    Button,
    TextField,
    Typography,
    Divider,
    CircularProgress,
    Alert,
    useTheme,
    alpha,
    Paper,
} from '@mui/material';
import LoginIcon from '@mui/icons-material/Login';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import StorageIcon from '@mui/icons-material/Storage';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { DataFormulatorState, dfActions, getSessionId } from '../app/dfSlice';
import { getUrls } from '../app/utils';
import { AppDispatch } from '../app/store';
import { toolName } from '../app/App';
import dfLogo from '../assets/df-logo.png';

interface LoginViewProps {
    onLoginSuccess: () => void;
    onGuestContinue: () => void;
    supersetEnabled: boolean;
}

export const LoginView: FC<LoginViewProps> = ({ onLoginSuccess, onGuestContinue, supersetEnabled }) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const dispatch = useDispatch<AppDispatch>();
    const serverConfig = useSelector((state: DataFormulatorState) => state.serverConfig);

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const popupRef = useRef<Window | null>(null);
    const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        return () => {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        };
    }, []);

    const handleSSOLogin = () => {
        setLoading(true);
        setError(null);

        const bridgeUrl = serverConfig.SSO_LOGIN_URL;
        if (!bridgeUrl) {
            setError(t('auth.ssoFailed', { message: 'SSO not configured' }));
            setLoading(false);
            return;
        }

        const dfOrigin = encodeURIComponent(window.location.origin);
        const ssoUrl = `${bridgeUrl}?df_origin=${dfOrigin}`;

        const width = 600;
        const height = 700;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;
        const popup = window.open(
            ssoUrl,
            'df-sso-login',
            `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
        );

        if (!popup) {
            setError(t('auth.ssoPopupBlocked'));
            setLoading(false);
            return;
        }

        popupRef.current = popup;

        const handleMessage = async (event: MessageEvent) => {
            if (event.data?.type !== 'df-sso-auth') return;

            window.removeEventListener('message', handleMessage);
            if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }

            const { access_token, refresh_token, user } = event.data;

            try {
                const resp = await fetch(getUrls().AUTH_SSO_SAVE_TOKENS, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token, refresh_token, user }),
                });
                const data = await resp.json();

                if (data.status === 'ok') {
                    await dispatch(getSessionId()).unwrap();
                    const configResp = await fetch(getUrls().APP_CONFIG, { credentials: 'include' });
                    const configData = await configResp.json();
                    dispatch(dfActions.setServerConfig(configData));
                    onLoginSuccess();
                } else {
                    setError(data.message || t('auth.ssoFailed', { message: 'Unknown error' }));
                }
            } catch (err: any) {
                setError(err.message || 'Network error');
            } finally {
                setLoading(false);
            }
        };

        window.addEventListener('message', handleMessage);

        pollTimerRef.current = setInterval(() => {
            if (popup.closed) {
                if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
                window.removeEventListener('message', handleMessage);
                setLoading(false);
            }
        }, 1000);
    };

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!username || !password) return;

        setLoading(true);
        setError(null);

        try {
            const response = await fetch(getUrls().AUTH_LOGIN, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();

            if (data.status === 'ok') {
                await dispatch(getSessionId()).unwrap();
                const configResp = await fetch(getUrls().APP_CONFIG, { credentials: 'include' });
                const configData = await configResp.json();
                dispatch(dfActions.setServerConfig(configData));
                onLoginSuccess();
            } else {
                setError(data.message || 'Login failed');
            }
        } catch (err: any) {
            setError(err.message || 'Network error');
        } finally {
            setLoading(false);
        }
    };

    const handleGuest = async () => {
        await dispatch(getSessionId()).unwrap();
        onGuestContinue();
    };

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                height: '100%',
                overflowY: 'auto',
                background: `
                    linear-gradient(90deg, ${alpha(theme.palette.text.secondary, 0.01)} 1px, transparent 1px),
                    linear-gradient(0deg, ${alpha(theme.palette.text.secondary, 0.01)} 1px, transparent 1px)
                `,
                backgroundSize: '16px 16px',
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    maxWidth: 420,
                    width: '100%',
                    mx: 2,
                    p: 5,
                    border: `1px solid ${alpha(theme.palette.divider, 0.12)}`,
                    borderRadius: 2,
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Box component="img" sx={{ height: 28, mr: 1 }} alt="" src={dfLogo} />
                    <Typography
                        component="h1"
                        sx={{ fontWeight: 300, letterSpacing: '0.03em', fontSize: 22 }}
                    >
                        {toolName}
                    </Typography>
                </Box>

                <Typography
                    variant="body2"
                    sx={{ color: 'text.secondary', mb: 3, textAlign: 'center' }}
                >
                    {t('auth.loginSubtitle')}
                </Typography>

                {supersetEnabled ? (
                    <>
                        {error && (
                            <Alert severity="error" sx={{ fontSize: 13, width: '100%', mb: 1 }}>
                                {t('auth.loginFailed', { message: error })}
                            </Alert>
                        )}

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, width: '100%' }}>
                            <StorageIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                                {t('auth.supersetConnection')}
                            </Typography>
                        </Box>

                        {serverConfig.SSO_LOGIN_URL && (
                            <>
                                <Button
                                    variant="contained"
                                    color="primary"
                                    disabled={loading}
                                    onClick={handleSSOLogin}
                                    startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <OpenInNewIcon />}
                                    sx={{ textTransform: 'none', width: '100%' }}
                                    fullWidth
                                >
                                    {loading ? t('auth.ssoLoggingIn') : t('auth.ssoLogin')}
                                </Button>
                                <Typography variant="caption" sx={{ color: 'text.secondary', mt: 1, textAlign: 'center' }}>
                                    {t('auth.ssoDescription')}
                                </Typography>

                                <Divider sx={{ my: 1.5, width: '100%' }}>
                                    <Typography variant="body2" sx={{ color: 'text.secondary', px: 1, fontSize: 12 }}>
                                        {t('auth.ssoOrPassword')}
                                    </Typography>
                                </Divider>
                            </>
                        )}

                        <Box
                            component="form"
                            onSubmit={handleLogin}
                            sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}
                        >
                            <TextField
                                size="small"
                                label={t('auth.username')}
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                autoComplete="username"
                                autoFocus
                                fullWidth
                            />
                            <TextField
                                size="small"
                                label={t('auth.password')}
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoComplete="current-password"
                                fullWidth
                            />

                            <Button
                                type="submit"
                                variant={serverConfig.SSO_LOGIN_URL ? "outlined" : "contained"}
                                color="primary"
                                disabled={loading || !username || !password}
                                startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <LoginIcon />}
                                sx={{ textTransform: 'none', mt: 0.5 }}
                                fullWidth
                            >
                                {loading ? t('auth.signingIn') : t('auth.signIn')}
                            </Button>
                        </Box>

                        <Divider sx={{ my: 3, width: '100%' }}>
                            <Typography variant="body2" sx={{ color: 'text.secondary', px: 1 }}>
                                {t('auth.or')}
                            </Typography>
                        </Divider>
                    </>
                ) : (
                    <Alert severity="info" sx={{ mb: 2, width: '100%', fontSize: 13 }}>
                        {t('auth.notConfigured')}
                    </Alert>
                )}

                <Button
                    variant="outlined"
                    color="primary"
                    onClick={handleGuest}
                    startIcon={<PersonOutlineIcon />}
                    sx={{ textTransform: 'none', width: '100%' }}
                    fullWidth
                >
                    {t('auth.continueAsGuest')}
                </Button>
                <Typography variant="caption" sx={{ color: 'text.secondary', mt: 1, textAlign: 'center' }}>
                    {t('auth.guestDescription')}
                </Typography>
            </Paper>
        </Box>
    );
};
