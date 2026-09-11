--
-- PostgreSQL database dump
--

\restrict H40v8GJJ7RRGwLSiABwfp3U1eT9tWPB4BrRuonNaPx2trVwqC7O9QizJwkfCEYw

-- Dumped from database version 18.1 (Debian 18.1-1.pgdg13+2)
-- Dumped by pg_dump version 18.1 (Debian 18.1-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: paises; Type: TABLE; Schema: public; Owner: alumno
--

CREATE TABLE public.paises (
    pais_id integer NOT NULL,
    pais_nombre character varying(50) NOT NULL,
    pais_codigo character varying(5) NOT NULL
);


ALTER TABLE public.paises OWNER TO alumno;

--
-- Name: personas; Type: TABLE; Schema: public; Owner: alumno
--

CREATE TABLE public.personas (
    persona_id integer NOT NULL,
    nombre character varying(50) NOT NULL,
    primer_apellido character varying(50) NOT NULL,
    segundo_apellido character varying(50),
    ci character varying(20) NOT NULL
);


ALTER TABLE public.personas OWNER TO alumno;

--
-- Name: personas_persona_id_seq; Type: SEQUENCE; Schema: public; Owner: alumno
--

CREATE SEQUENCE public.personas_persona_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.personas_persona_id_seq OWNER TO alumno;

--
-- Name: personas_persona_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alumno
--

ALTER SEQUENCE public.personas_persona_id_seq OWNED BY public.personas.persona_id;


--
-- Name: viajes; Type: TABLE; Schema: public; Owner: alumno
--

CREATE TABLE public.viajes (
    viaje_id integer NOT NULL,
    persona_id integer NOT NULL,
    pais_id integer NOT NULL,
    fecha_llegada date NOT NULL
);


ALTER TABLE public.viajes OWNER TO alumno;

--
-- Name: viajes_viaje_id_seq; Type: SEQUENCE; Schema: public; Owner: alumno
--

CREATE SEQUENCE public.viajes_viaje_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.viajes_viaje_id_seq OWNER TO alumno;

--
-- Name: viajes_viaje_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: alumno
--

ALTER SEQUENCE public.viajes_viaje_id_seq OWNED BY public.viajes.viaje_id;


--
-- Name: personas persona_id; Type: DEFAULT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.personas ALTER COLUMN persona_id SET DEFAULT nextval('public.personas_persona_id_seq'::regclass);


--
-- Name: viajes viaje_id; Type: DEFAULT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.viajes ALTER COLUMN viaje_id SET DEFAULT nextval('public.viajes_viaje_id_seq'::regclass);


--
-- Data for Name: paises; Type: TABLE DATA; Schema: public; Owner: alumno
--

COPY public.paises (pais_id, pais_nombre, pais_codigo) FROM stdin;
1	Bolivia	BOL
2	Argentina	ARG
3	Brasil	BRA
4	Chile	CHL
5	Peru	PER
6	Colombia	COL
7	Ecuador	ECU
8	Paraguay	PRY
9	Uruguay	URY
10	Venezuela	VEN
11	Mexico	MEX
12	Estados Unidos	USA
13	Espana	ESP
14	Francia	FRA
15	Alemania	DEU
16	Italia	ITA
17	Japon	JPN
18	China	CHN
19	Australia	AUS
20	Canada	CAN
\.


--
-- Data for Name: personas; Type: TABLE DATA; Schema: public; Owner: alumno
--

COPY public.personas (persona_id, nombre, primer_apellido, segundo_apellido, ci) FROM stdin;
1	pepe	cortizona	cortnza	123
\.


--
-- Data for Name: viajes; Type: TABLE DATA; Schema: public; Owner: alumno
--

COPY public.viajes (viaje_id, persona_id, pais_id, fecha_llegada) FROM stdin;
\.


--
-- Name: personas_persona_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alumno
--

SELECT pg_catalog.setval('public.personas_persona_id_seq', 1, true);


--
-- Name: viajes_viaje_id_seq; Type: SEQUENCE SET; Schema: public; Owner: alumno
--

SELECT pg_catalog.setval('public.viajes_viaje_id_seq', 1, false);


--
-- Name: paises paises_pkey; Type: CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.paises
    ADD CONSTRAINT paises_pkey PRIMARY KEY (pais_id);


--
-- Name: personas personas_ci_key; Type: CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_ci_key UNIQUE (ci);


--
-- Name: personas personas_pkey; Type: CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.personas
    ADD CONSTRAINT personas_pkey PRIMARY KEY (persona_id);


--
-- Name: viajes viajes_pkey; Type: CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.viajes
    ADD CONSTRAINT viajes_pkey PRIMARY KEY (viaje_id);


--
-- Name: idx_viajes_pais; Type: INDEX; Schema: public; Owner: alumno
--

CREATE INDEX idx_viajes_pais ON public.viajes USING btree (pais_id);


--
-- Name: idx_viajes_persona; Type: INDEX; Schema: public; Owner: alumno
--

CREATE INDEX idx_viajes_persona ON public.viajes USING btree (persona_id);


--
-- Name: viajes viajes_pais_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.viajes
    ADD CONSTRAINT viajes_pais_id_fkey FOREIGN KEY (pais_id) REFERENCES public.paises(pais_id) ON DELETE CASCADE;


--
-- Name: viajes viajes_persona_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: alumno
--

ALTER TABLE ONLY public.viajes
    ADD CONSTRAINT viajes_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(persona_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict H40v8GJJ7RRGwLSiABwfp3U1eT9tWPB4BrRuonNaPx2trVwqC7O9QizJwkfCEYw

