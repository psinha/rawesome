-- Copyright 2012-2013 Greg Horn
--
-- This file is part of rawesome.
--
-- rawesome is free software: you can redistribute it and/or modify
-- it under the terms of the GNU Lesser General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- rawesome is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU Lesser General Public License for more details.
--
-- You should have received a copy of the GNU Lesser General Public License
-- along with rawesome.  If not, see <http://www.gnu.org/licenses/>.

{-# OPTIONS_GHC -Wall #-}
{-# LANGUAGE DeriveDataTypeable #-}

module ParseArgs ( getip
                 ) where

import System.Console.CmdArgs

data VisArgs = VisArgs { ipfile :: String
                       , ip :: String
                       } deriving (Show, Data, Typeable)

myargs :: VisArgs
myargs = VisArgs { ipfile = "" &= help "file to read IP address out of" &= typ "FILENAME"
                 , ip = ""     &= help "an IP address" &= typ "ADDRESS"
                 } &= summary "the kite visualizer program"

getip :: String -> String -> IO String
getip programname defaultip = do
  a <- cmdArgs (myargs &= program programname)
  case (ipfile a,ip a) of
    ("","") -> return defaultip
    ("",x) -> return x
    (f,"") -> fmap (head . lines) (readFile f)
    (_,_) -> error "please only specify your ip address one way"
--  
--main :: IO ()
--main = do
--  ip' <- getip "defaultip"
--  print ip'
--  putStrLn "finished successfully"
